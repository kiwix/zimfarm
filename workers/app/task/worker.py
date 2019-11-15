#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import sys
import time
import signal
import shutil
import pathlib
import datetime

import requests
import humanfriendly

from common import logger
from common.worker import BaseWorker
from common.docker import (
    query_host_mounts,
    query_container_stats,
    start_dnscache,
    get_ip_address,
    start_scraper,
    start_uploader,
    RUNNING_STATUSES,
    get_container_logs,
    task_container_name,
)

SLEEP_INTERVAL = 60  # nb of seconds to sleep before watching
PENDING = "pending"
UPLOADING = "uploading"
UPLOADED = "uploaded"
FAILED = "failed"

started = "started"
scraper_started = "scraper_started"
scraper_completed = "scraper_completed"


class TaskWorker(BaseWorker):
    def __init__(self, **kwargs):

        # print config
        self.print_config(**kwargs)

        # check workdir
        self.check_workdir()

        # check SSH private key
        self.check_private_key()

        # ensure we have valid credentials
        self.check_auth()

        # ensure we have access to docker API
        self.check_docker()

        cont_stats = query_container_stats(self.workdir)
        logger.info(
            "Container resources:"
            "\n\tRAM  (total): {mem_total}"
            "\n\tRAM  (avail): {mem_avail}"
            "\n\tCPUs: {cpu_total}"
            "\n\tDisk: {disk_avail}".format(
                mem_total=humanfriendly.format_size(
                    cont_stats["memory"]["total"], binary=True
                ),
                mem_avail=humanfriendly.format_size(
                    cont_stats["memory"]["available"], binary=True
                ),
                cpu_total=cont_stats["cpu"]["total"],
                disk_avail=humanfriendly.format_size(
                    cont_stats["disk"]["available"], binary=True
                ),
            )
        )

        self.task = None
        self.should_stop = False
        self.task_wordir = None
        self.host_task_workdir = None  # path on host for task_dir

        self.dnscache = None  # dnscache container
        self.dns = None  # list of DNS IPs or None

        self.zim_files = {}  # ZIM files registry
        self.uploader = None  # zim-files uploader container

        self.scraper = None  # scraper container
        self.log_uploader = None  # scraper log uploader container
        self.host_logsdir = None  # path on host where logs are stored
        self.scraper_succeeded = None  # whether scraper succeeded

        # register stop/^C
        self.register_signals()

    def get_task(self):
        logger.info(f"Fetching task details for {self.task_id}")
        success, status_code, response = self.query_api("GET", f"/tasks/{self.task_id}")
        if success and status_code == requests.codes.OK:
            self.task = response
            return

        if status_code == requests.codes.NOT_FOUND:
            logger.warning(f"task #{self.task_id} doesn't exist")
        else:
            logger.warning(f"couldn't retrieve task detail for #{self.task_id}")

    def mark_task_started(self):
        logger.info(f"Updating task-status={started}")
        success, status_code, response = self.query_api(
            "PATCH", f"/tasks/{self.task_id}", payload={"event": started, "payload": {}}
        )
        if success and status_code == requests.codes.OK:
            return
        logger.warning(f"couldn't set task status={started}")

    def mark_scraper_started(self):
        logger.info(f"Updating task-status={scraper_started}")
        self.scraper.reload()
        success, status_code, response = self.query_api(
            "PATCH",
            f"/tasks/{self.task_id}",
            payload={
                "event": scraper_started,
                "payload": {
                    "image": self.scraper.image.tags[-1],
                    "command": self.scraper.attrs["Config"]["Cmd"],
                    "log": pathlib.Path(self.scraper.attrs["LogPath"]).name,
                },
            },
        )
        if success and status_code == requests.codes.OK:
            return
        logger.warning(f"couldn't set task status={scraper_started}")

    def mark_scraper_completed(self, exit_code):
        logger.info(f"Updating task-status={scraper_completed}")
        success, status_code, response = self.query_api(
            "PATCH",
            f"/tasks/{self.task_id}",
            payload={"event": scraper_completed, "payload": {"exit_code": exit_code}},
        )
        if success and status_code == requests.codes.OK:
            return
        logger.warning(f"couldn't set task status={scraper_completed}")

    def mark_task_completed(self, status, exception=None, traceback=None):
        logger.info(f"Updating task-status={status}")
        event_payload = {}
        if exception:
            event_payload["exception"] = exception
        if traceback:
            event_payload["traceback"] = traceback

        event_payload["log"] = get_container_logs(
            self.docker, task_container_name(self.task_id), tail=2000
        )

        success, status_code, response = self.query_api(
            "PATCH",
            f"/tasks/{self.task_id}",
            payload={"event": status, "payload": event_payload},
        )
        if success and status_code == requests.codes.OK:
            return
        logger.warning(
            f"couldn't set task status={status} HTTP {status_code}: {response}"
        )

    def mark_file_created(self, filename, filesize):
        human_fsize = humanfriendly.format_size(filesize, binary=True)
        logger.info(f"ZIM file created: {filename}, {human_fsize}")
        success, status_code, response = self.query_api(
            "PATCH",
            f"/tasks/{self.task_id}",
            payload={
                "event": "created_file",
                "payload": {"file": {"name": filename, "size": filesize}},
            },
        )
        if success and status_code == requests.codes.OK:
            return
        logger.warning(f"couldn't send file-created event")

    def mark_file_uploaded(self, filename):
        logger.info(f"Updating file-status=uploaded for {filename}")
        success, status_code, response = self.query_api(
            "PATCH",
            f"/tasks/{self.task_id}",
            payload={"event": "uploaded_file", "payload": {"filename": filename}},
        )
        if success and status_code == requests.codes.OK:
            return
        logger.warning(f"couldn't update file upload status")

    def setup_workdir(self):
        logger.info("Setting-up workdir")
        folder_name = f"{self.task_id}"
        host_mounts = query_host_mounts(self.docker, self.workdir)

        self.task_wordir = self.workdir.joinpath(folder_name)
        self.task_wordir.mkdir(exist_ok=True)
        self.host_task_workdir = host_mounts[self.workdir].joinpath(folder_name)

    def cleanup_workdir(self):
        logger.info(f"Removing task workdir {self.workdir}")
        zim_files = [
            (f.name, humanfriendly.format_size(f.stat().st_size, binary=True))
            for f in self.task_wordir.glob("*.zim")
        ]
        if zim_files:
            logger.error(f"ZIM files exists ; __NOT__ removing: {zim_files}")
            return False
        try:
            shutil.rmtree(self.task_wordir)
        except Exception as exc:
            logger.error(f"Failed to remove workdir: {exc}")

    def start_dnscache(self):
        logger.info(f"Starting DNS cache")
        self.dnscache = start_dnscache(self.docker, self.task)
        self.dns = [get_ip_address(self.docker, self.dnscache.name)]
        logger.debug(f"DNS Cache started using IPs: {self.dns}")

    def stop_dnscache(self, timeout=None):
        logger.info("Stopping and removing DNS cache")
        if self.dnscache:
            self.dnscache.stop(timeout=timeout)

    def start_scraper(self):
        logger.info(f"Starting scraper. Expects files at: {self.host_task_workdir} ")
        self.scraper = start_scraper(
            self.docker, self.task, self.dns, self.host_task_workdir
        )

    def stop_scraper(self, timeout=None):
        logger.info("Stopping and removing scraper")
        if self.scraper:
            self.scraper.stop(timeout=timeout)
            self.scraper.remove()

    def update(self):
        # update scraper
        self.scraper.reload()
        self.dnscache.reload()
        self.uploader.reload()
        self.refresh_files_list()

    def stop(self, timeout=1):
        """ stopping everything before exit (on term or end of task) """
        logger.info("Stopping all containers and actions")
        self.should_stop = True
        self.stop_scraper(timeout)
        self.stop_dnscache(timeout)
        self.stop_uploader(timeout)

    def exit_gracefully(self, signum, frame):
        signame = signal.strsignal(signum)
        logger.info(f"received exit signal ({signame}), shutting down…")
        self.stop()
        self.cleanup_workdir()
        self.mark_task_completed("canceled")
        sys.exit(1)

    def shutdown(self, status, **kwargs):
        logger.info("Shutting down task-worker")
        self.stop()
        self.cleanup_workdir()
        self.mark_task_completed(status, **kwargs)

    def start_uploader(self, upload_dir, filename, move, delete):
        logger.info(
            f"Starting uploader for /{upload_dir}/{filename} – move={move}, delete={delete}"
        )
        self.uploader = start_uploader(
            self.docker,
            self.task,
            self.username,
            self.host_task_workdir,
            upload_dir,
            filename,
            move,
            delete,
        )

    def stop_uploader(self, timeout=None):
        logger.info("Stopping and removing uploader")
        if self.uploader:
            self.uploader.stop(timeout=timeout)
            self.uploader.remove()

    @property
    def scraper_running(self):
        """ wether scraper container is still running or not """
        if not self.scraper:
            return False
        self.scraper.reload()
        return self.scraper.status in RUNNING_STATUSES

    @property
    def uploader_running(self):
        if not self.uploader:
            return False
        self.uploader.reload()
        return self.uploader.status in RUNNING_STATUSES

    def refresh_files_list(self):
        for fpath in self.task_wordir.glob("*.zim"):
            if fpath.name not in self.zim_files.keys():
                # append file to our watchlist
                self.zim_files.update({fpath.name: PENDING})
                # inform API about new file
                self.mark_file_created(fpath.name, fpath.stat().st_size)

    @property
    def pending_zim_files(self):
        """ shortcut list of watched file in PENDING status """
        return list(filter(lambda x: x[1] == PENDING, self.zim_files.items()))

    def upload_files(self):
        """ manages self.zim_files

            - list files in folder to upload list
            - upload files one by one using dedicated uploader containers """
        # check files in workdir and update our list of files to upload
        self.refresh_files_list()

        # check if uploader running
        if self.uploader:
            self.uploader.reload()

        if self.uploader and self.uploader.status in RUNNING_STATUSES:
            # still running, nothing to do
            return

        # not running but _was_ running
        if self.uploader:
            # find file
            zim_file = self.uploader.labels["filename"]
            # get result of container
            if self.uploader.attrs["State"]["ExitCode"] == 0:
                self.zim_files[zim_file] = UPLOADED
                self.mark_file_uploaded(zim_file)
            else:
                self.zim_files[zim_file] = FAILED
                logger.error(f"ZIM Uploader:: {self.uploader.logs()}")
            self.uploader.remove()
            self.uploader = None

        # start an uploader instance
        if self.uploader is None and self.pending_zim_files and not self.should_stop:
            try:
                zim_file, _ = self.pending_zim_files.pop()
            except Exception:
                # no more pending files,
                logger.debug("failed to get ZIM file: pending_zim_files empty")
            else:
                self.start_uploader(
                    f"zim{self.task['config']['warehouse_path']}",
                    zim_file,
                    move=True,
                    delete=True,
                )
                self.zim_files[zim_file] = UPLOADING

    def upload_log(self):
        if not self.scraper:
            # no more scraper, can't do.
            return

        log_path = pathlib.Path(self.scraper.attrs["LogPath"])
        host_logsdir = log_path.parent
        filename = log_path.name

        if self.log_uploader:
            self.log_uploader.reload()

            if self.log_uploader.status in RUNNING_STATUSES:
                # still uploading
                return
            self.log_uploader = None

        self.log_uploader = start_uploader(
            self.docker,
            self.task,
            self.username,
            host_logsdir,
            "logs",
            filename,
            move=False,
            delete=False,
        )

    def handle_stopped_scraper(self):
        self.scraper.reload()
        exit_code = self.scraper.attrs["State"]["ExitCode"]
        self.mark_scraper_completed(exit_code)
        self.scraper_succeeded = exit_code == 0
        self.upload_log()
        logger.info("Waiting for scraper log to finish uploading")
        if self.log_uploader:
            exit_code = self.log_uploader.wait()["StatusCode"]
            logger.info(f"Scraper log upload complete: {exit_code}")
            if exit_code != 0:
                logger.error(f"Log Uploader:: {self.log_uploader.logs()}")

    def sleep(self):
        time.sleep(1)

    def run(self):

        # get task detail from URL
        self.get_task()
        if self.task is None:
            logger.critical("Can't do much without task detail. exitting.")
            return 1
        self.mark_task_started()

        # prepare sub folder
        self.setup_workdir()

        # start our DNS cache
        self.start_dnscache()

        # start scraper
        self.start_scraper()
        self.mark_scraper_started()

        last_check = datetime.datetime.now()

        while not self.should_stop and self.scraper_running:
            now = datetime.datetime.now()
            if (now - last_check).total_seconds() < SLEEP_INTERVAL:
                self.sleep()
                continue

            self.upload_log()

            self.upload_files()

        # scraper is done. check files so upload can continue
        self.handle_stopped_scraper()

        self.upload_files()  # rescan folder

        # monitor upload of files
        while not self.should_stop and (
            self.pending_zim_files or self.uploader_running
        ):
            now = datetime.datetime.now()
            if (now - last_check).total_seconds() < SLEEP_INTERVAL:
                self.sleep()
                continue

            self.upload_files()

        self.upload_files()  # make sure we submit upload status for last one

        # done with processing, cleaning-up and exiting
        self.shutdown("succeeded" if self.scraper_succeeded else "failed")
