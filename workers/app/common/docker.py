#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import os
import time
import uuid
import pathlib

import docker
from docker.types import Mount

from common import logger
from common.constants import (
    DEFAULT_CPU_SHARE,
    CONTAINER_SCRAPER_IDENT,
    ZIMFARM_DISK_SPACE,
    ZIMFARM_CPUS,
    ZIMFARM_MEMORY,
    CONTAINER_TASK_IDENT,
    USE_PUBLIC_DNS,
    CONTAINER_DNSCACHE_IDENT,
    TASK_WORKER_IMAGE,
    DOCKER_SOCKET,
    PRIVATE_KEY,
    UPLOAD_URI,
    DNSCACHE_IMAGE,
    UPLOADER_IMAGE,
)
from common.utils import short_id, as_pos_int, format_size

RUNNING_STATUSES = ("created", "running", "restarting", "paused", "removing")
STOPPED_STATUSES = ("exited", "dead")
DOCKER_API_RETRIES = 10  # retry attempts in case of API error
RESOURCES_DISK_LABEL = "resources_disk"


def retried_docker_call(docker_method, *args, **kwargs):
    attempt = 0
    while True:
        attempt += 1
        try:
            return docker_method(*args, **kwargs)
        # including ImageNotFound as per #456
        # most 404 errors would be from incorrect image/tag name but we still want to
        # avoid crashing on 404 due to temporary docker-hub issues
        except (docker.errors.APIError, docker.errors.ImageNotFound) as exc:
            if exc.is_server_error() and attempt <= DOCKER_API_RETRIES:
                logger.debug(
                    f"Docker API Error for {docker_method} (attempt {attempt}): {exc}"
                )
                time.sleep(10 * attempt)
                continue
            raise exc


# following functions are proxies to API using retried calls
# to prevent failures due to HTTP 500 fromt the API.
# > docker sometimes have difficulties responding and requires a retry
# def inspect_container(docker_client, *args, **kwargs):
#     """ container="" """
#     return retried_docker_call(docker_client.api.inspect_container, *args, **kwargs)


# def list_containers_raw(docker_client, *args, **kwargs):
#     """ quiet=False, all=False, trunc=False, latest=False, since=None,
#         before=None, limit=-1, size=False, filters=None """
#     return retried_docker_call(docker_client.api.containers, *args, **kwargs)


def get_image(docker_client, *args, **kwargs):
    """ name="" """
    return retried_docker_call(docker_client.images.get, *args, **kwargs)


def pull_image(docker_client, *args, **kwargs):
    """ repository="", tag=None """
    return retried_docker_call(docker_client.images.pull, *args, **kwargs)


def run_container(docker_client, *args, **kwargs):
    """image, command=None
    https://docker-py.readthedocs.io/en/stable/containers.html#docker.models.containers.ContainerCollection.run"""
    return retried_docker_call(docker_client.containers.run, *args, **kwargs)


def get_container(docker_client, *args, **kwargs):
    """ id_or_name="" """
    container = retried_docker_call(docker_client.containers.get, *args, **kwargs)
    # save a very frequent call to reload()
    container.reload()
    return container


def list_containers(docker_client, *args, **kwargs):
    """ all=False, since="Id or name", before="Id or name", limit=None, filters={} """
    return retried_docker_call(docker_client.containers.list, *args, **kwargs)


def remove_container(docker_client, *args, **kwargs):
    """ container="", v=False, link=False, force=False """
    return retried_docker_call(docker_client.api.remove_container, *args, **kwargs)


def prune_containers(docker_client, *args, **kwargs):
    """ filters={} """
    return retried_docker_call(docker_client.api.prune_containers, *args, **kwargs)


def stop_container(docker_client, *args, **kwargs):
    """ container="", timeout=None """
    return retried_docker_call(docker_client.api.stop, *args, **kwargs)


def wait_container(docker_client, *args, **kwargs):
    """ container="", timeout=None, condition="" """
    return retried_docker_call(docker_client.api.wait, *args, **kwargs)


def container_logs(docker_client, *args, **kwargs):
    """container, stdout=True, stderr=True, stream=False, timestamps=False,
    tail='all', since=None, follow=None, until=None"""
    return retried_docker_call(docker_client.api.logs, *args, **kwargs)


def get_or_pull_image(docker_client, tag):
    """ attempt to get locally or pull and return. Tag is repo:tag """
    try:
        return get_image(docker_client, tag)
    except docker.errors.ImageNotFound:
        return pull_image(docker_client, tag)


def query_containers_resources(docker_client):
    cpu_shares = 0
    memory = 0
    disk = 0
    for container in list_containers(
        docker_client, filters={"name": CONTAINER_SCRAPER_IDENT}
    ):
        container.reload()
        cpu_shares += container.attrs["HostConfig"]["CpuShares"] or DEFAULT_CPU_SHARE
        memory += container.attrs["HostConfig"]["Memory"]
        try:
            disk += int(container.labels.get(RESOURCES_DISK_LABEL, 0))
        except Exception:
            disk += 0  # improper label

    return {"cpu_shares": cpu_shares, "memory": memory, "disk": disk}


def query_host_stats(docker_client, workdir):

    # query cpu and ram usage in our containers
    stats = query_containers_resources(docker_client)

    # disk space
    workir_fs_stats = os.statvfs(workdir)
    disk_used = stats["disk"]
    disk_free = workir_fs_stats.f_bavail * workir_fs_stats.f_frsize

    # CPU cores
    cpu_used = stats["cpu_shares"] // DEFAULT_CPU_SHARE
    cpu_avail = as_pos_int(ZIMFARM_CPUS - cpu_used)

    # RAM
    mem_used = stats["memory"]
    mem_avail = as_pos_int(ZIMFARM_MEMORY - mem_used)

    return {
        "cpu": {"total": ZIMFARM_CPUS, "used": cpu_used, "available": cpu_avail},
        "disk": {
            "total": ZIMFARM_DISK_SPACE,
            "used": disk_used,
            "available": disk_free,
        },
        "memory": {"total": ZIMFARM_MEMORY, "used": mem_used, "available": mem_avail},
    }


def query_container_stats(workdir):
    workir_fs_stats = os.statvfs(workdir)
    avail_disk = workir_fs_stats.f_bavail * workir_fs_stats.f_frsize

    with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r") as fp:
        mem_total = int(fp.read().strip())
    with open("/sys/fs/cgroup/memory/memory.usage_in_bytes", "r") as fp:
        mem_used = int(fp.read().strip())
    mem_avail = mem_total - mem_used

    with open("/sys/fs/cgroup/cpuacct/cpuacct.usage_percpu", "r") as fp:
        cpu_total = len(fp.read().strip().split())

    return {
        "cpu": {"total": cpu_total},
        "disk": {"available": avail_disk},
        "memory": {"total": mem_total, "available": mem_avail},
    }


def query_host_mounts(docker_client, workdir=None):
    keys = [DOCKER_SOCKET, PRIVATE_KEY]
    if workdir:
        keys.append(workdir)
    container = get_container(docker_client, os.getenv("HOSTNAME"))
    mounts = {}
    for mount in container.attrs["Mounts"]:
        dest = pathlib.Path(mount["Destination"])
        if dest in keys:
            key = keys[keys.index(dest)]
            mounts[key] = pathlib.Path(mount["Source"])
    return mounts


def task_container_name(task_id):
    return f"{short_id(task_id)}_{CONTAINER_TASK_IDENT}"


def dnscache_container_name(task_id):
    return f"{short_id(task_id)}_{CONTAINER_DNSCACHE_IDENT}"


def scraper_container_name(task_id, task_name):
    return f"{short_id(task_id)}_{CONTAINER_SCRAPER_IDENT}_{task_name}"


def upload_container_name(task_id, filename, unique):
    ident = "zimup" if filename.endswith(".zim") else "logup"
    if unique:
        filename = f"{uuid.uuid4().hex}{pathlib.Path(filename).suffix}"
    return f"{short_id(task_id)}_{ident}_{filename}"


def get_ip_address(docker_client, name):
    """ IP Address (first) of a named container """
    return get_container(docker_client, name).attrs["NetworkSettings"]["IPAddress"]


def get_label_value(docker_client, name, label):
    """ direct access to a single label value """
    return get_container(docker_client, name).attrs["Config"]["Labels"].get(label)


def start_dnscache(docker_client, task):
    name = dnscache_container_name(task["_id"])
    environment = {"USE_PUBLIC_DNS": "yes" if USE_PUBLIC_DNS else "no"}
    image = get_or_pull_image(docker_client, DNSCACHE_IMAGE)
    return run_container(
        docker_client,
        image=image,
        detach=True,
        name=name,
        environment=environment,
        remove=True,
        labels={
            "zimfarm": "",
            "task_id": task["_id"],
            "tid": short_id(task["_id"]),
            "schedule_name": task["schedule_name"],
        },
    )


def start_scraper(docker_client, task, dns, host_workdir):
    config = task["config"]
    offliner = config["task_name"]
    container_name = scraper_container_name(task["_id"], offliner)

    # remove container should it exists (should not)
    try:
        remove_container(docker_client, container_name)
    except docker.errors.NotFound:
        pass

    # scraper is systematically pulled before starting
    tag = f'{config["image"]["name"]}:{config["image"]["tag"]}'
    logger.debug(f"Pulling image {tag}")
    docker_image = pull_image(docker_client, tag)

    # where to mount volume inside scraper
    mount_point = config["mount_point"]

    # mounts will be attached to host's fs, not this one
    mounts = [Mount(str(mount_point), str(host_workdir), type="bind")]

    command = config["str_command"]
    cpu_shares = config["resources"]["cpu"] * DEFAULT_CPU_SHARE
    mem_limit = config["resources"]["memory"]
    disk_limit = config["resources"]["disk"]
    shm_size = config["resources"].get("shm")
    cap_add = config["resources"].get("cap_add", [])
    cap_drop = config["resources"].get("cap_drop", [])

    return run_container(
        docker_client,
        image=docker_image,
        command=command,
        cpu_shares=cpu_shares,
        mem_limit=mem_limit,
        dns=dns,
        detach=True,
        labels={
            "zimfarm": "",
            "zimscraper": "yes",
            "task_id": task["_id"],
            "tid": short_id(task["_id"]),
            "schedule_name": task["schedule_name"],
            RESOURCES_DISK_LABEL: str(disk_limit),
            "human.cpu": str(config["resources"]["cpu"]),
            "human.memory": format_size(mem_limit),
            "human.disk": format_size(disk_limit),
        },
        mem_swappiness=0,
        shm_size=shm_size,
        cap_add=cap_add,
        cap_drop=cap_drop,
        mounts=mounts,
        name=container_name,
        remove=False,  # scaper container will be removed once log&zim handled
    )


def start_task_worker(docker_client, task, webapi_uri, username, workdir, worker_name):
    container_name = task_container_name(task["_id"])

    # remove container should it exists (should not)
    try:
        remove_container(docker_client, container_name)
    except docker.errors.NotFound:
        pass

    logger.debug(f"getting image {TASK_WORKER_IMAGE}")
    # task worker is always pulled to ensure we can update our code
    if ":" not in TASK_WORKER_IMAGE:
        # consider missing :tag info as a local image for tests
        docker_image = get_image(docker_client, TASK_WORKER_IMAGE)
    else:
        docker_image = pull_image(docker_client, TASK_WORKER_IMAGE)

    # mounts will be attached to host's fs, not this one
    host_mounts = query_host_mounts(docker_client, workdir)
    host_task_workdir = str(host_mounts.get(workdir))
    host_docker_socket = str(host_mounts.get(DOCKER_SOCKET))
    host_private_key = str(host_mounts.get(PRIVATE_KEY))
    mounts = [
        Mount(str(workdir), host_task_workdir, type="bind"),
        Mount(str(DOCKER_SOCKET), host_docker_socket, type="bind", read_only=True),
        Mount(str(PRIVATE_KEY), host_private_key, type="bind", read_only=True),
    ]
    command = ["task-worker", "--task-id", task["_id"]]

    logger.debug(f"running {command}")
    return run_container(
        docker_client,
        image=docker_image,
        command=command,
        detach=True,
        environment={
            "USERNAME": username,
            "WORKDIR": str(workdir),
            "WEB_API_URI": webapi_uri,
            "UPLOAD_URI": UPLOAD_URI,
            "WORKER_NAME": worker_name,
            "ZIMFARM_DISK": os.getenv("ZIMFARM_DISK"),
            "ZIMFARM_CPUS": os.getenv("ZIMFARM_CPUS"),
            "ZIMFARM_MEMORY": os.getenv("ZIMFARM_MEMORY"),
            "DEBUG": os.getenv("DEBUG"),
            "USE_PUBLIC_DNS": "1" if USE_PUBLIC_DNS else "",
        },
        labels={
            "zimfarm": "",
            "zimtask": "yes",
            "task_id": task["_id"],
            "tid": short_id(task["_id"]),
            "schedule_name": task["schedule_name"],
        },
        mem_swappiness=0,
        mounts=mounts,
        name=container_name,
        remove=False,  # zimtask containers are pruned periodically
    )


def stop_task_worker(docker_client, task_id, timeout: int = 20):
    container_name = task_container_name(task_id)
    try:
        stop_container(docker_client, container_name, timeout=timeout)
    except docker.errors.NotFound:
        return False
    else:
        return True


def start_uploader(
    docker_client,
    task,
    username,
    host_workdir,
    upload_dir,
    filename,
    move,
    delete,
    compress,
    resume,
    watch,
):
    container_name = upload_container_name(task["_id"], filename, False)

    # remove container should it exists (should not)
    try:
        remove_container(docker_client, container_name)
        prune_containers(docker_client, {"label": [f"filename={filename}"]})
    except docker.errors.NotFound:
        pass

    docker_image = get_or_pull_image(docker_client, UPLOADER_IMAGE)

    # in container paths
    workdir = pathlib.Path("/data")
    filepath = workdir.joinpath(filename)

    host_mounts = query_host_mounts(docker_client)
    host_private_key = str(host_mounts[PRIVATE_KEY])
    mounts = [
        Mount(str(workdir), str(host_workdir), type="bind", read_only=not delete),
        Mount(str(PRIVATE_KEY), host_private_key, type="bind", read_only=True),
    ]

    command = [
        "uploader",
        "--file",
        str(filepath),
        "--upload-uri",
        f"{UPLOAD_URI}/{upload_dir}/{filepath.name}",
        "--username",
        username,
    ]
    if compress:
        command.append("--compress")
    if resume:
        command.append("--resume")
    if move:
        command.append("--move")
    if delete:
        command.append("--delete")
    if watch:
        command += ["--watch", str(watch)]

    return run_container(
        docker_client,
        image=docker_image,
        command=command,
        detach=True,
        environment={"RSA_KEY": str(PRIVATE_KEY)},
        labels={
            "zimfarm": "",
            "task_id": task["_id"],
            "tid": short_id(task["_id"]),
            "schedule_name": task["schedule_name"],
            "filename": filename,
        },
        mem_swappiness=0,
        mounts=mounts,
        name=container_name,
        remove=False,
    )


def get_container_logs(docker_client, container_name, tail="all"):
    try:
        return container_logs(
            docker_client, container_name, stdout=True, stderr=True, tail=tail
        ).decode("UTF-8")
    except docker.errors.NotFound:
        return f"Container `{container_name}` gone. Can't get logs"
    except Exception as exc:
        return f"Unable to get logs for `{container_name}`: {exc}"
