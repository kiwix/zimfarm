#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import os
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
)
from common.utils import short_id
from common.offliners import mount_point_for, command_for

RUNNING_STATUSES = ("created", "running", "restarting", "paused")
STOPPED_STATUSES = ("exited", "dead", "removing")


def query_containers_resources(docker_api):
    cpu_shares = 0
    memory = 0
    disk = 0
    for container in docker_api.containers(filters={"name": CONTAINER_SCRAPER_IDENT}):
        inspect_data = docker_api.inspect_container(container["Id"])
        cpu_shares += inspect_data["HostConfig"]["CpuShares"] or DEFAULT_CPU_SHARE
        memory += inspect_data["HostConfig"]["Memory"]
        try:
            disk += int(container["Labels"].get("resources_disk", 0))
        except Exception:
            disk += 0  # improper label

    return {"cpu_shares": cpu_shares, "memory": memory, "disk": disk}


def query_host_stats(docker_api, workdir):

    # query cpu and ram usage in our containers
    stats = query_containers_resources(docker_api)

    # disk space
    workir_fs_stats = os.statvfs(workdir)
    disk_free = workir_fs_stats.f_bavail * workir_fs_stats.f_frsize
    disk_avail = min([ZIMFARM_DISK_SPACE - stats["disk"], disk_free])

    # CPU cores
    cpu_used = stats["cpu_shares"] // DEFAULT_CPU_SHARE
    cpu_avail = ZIMFARM_CPUS - cpu_used

    # RAM
    mem_used = stats["memory"]
    mem_avail = ZIMFARM_MEMORY - mem_used

    return {
        "cpu": {"total": ZIMFARM_CPUS, "available": cpu_avail},
        "disk": {"total": ZIMFARM_DISK_SPACE, "available": disk_avail},
        "memory": {"total": ZIMFARM_MEMORY, "available": mem_avail},
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
    own_name = os.getenv("HOSTNAME")
    mounts = {}
    for mount in docker_client.api.inspect_container(own_name)["Mounts"]:
        dest = pathlib.Path(mount["Destination"])
        if dest in keys:
            key = keys[keys.index(dest)]
            mounts[key] = pathlib.Path(mount["Source"])
    return mounts


# def get_logs_host_dir(docker_client):
#     own_name = os.getenv("HOSTNAME")
#     return pathlib.Path(docker_client.api.inspect_container(own_name)["LogPath"]).parent


def task_container_name(task_id):
    return f"{short_id(task_id)}_{CONTAINER_TASK_IDENT}"


def dnscache_container_name(task_id):
    return f"{short_id(task_id)}_{CONTAINER_DNSCACHE_IDENT}"


def scraper_container_name(task_id, task_name):
    return f"{short_id(task_id)}_{CONTAINER_SCRAPER_IDENT}_{task_name}"


def upload_container_name(task_id, filename):
    ident = "zimup" if filename.endswith(".zim") else "logup"
    return f"{short_id(task_id)}_{ident}_{filename}"


def get_ip_address(docker_client, name):
    """ IP Address (first) of a named container """
    return docker_client.api.inspect_container(name)["NetworkSettings"]["IPAddress"]


def start_dnscache(docker_client, name):
    environment = {"USE_PUBLIC_DNS": "yes" if USE_PUBLIC_DNS else "no"}
    image = docker_client.images.pull("openzim/dnscache", tag="latest")
    return docker_client.containers.run(
        image, detach=True, name=name, environment=environment, remove=True
    )


def stop_container(docker_client, name, timeout):
    container = docker_client.get(name)
    container.stop(timeout=timeout)


def start_scraper(docker_client, task, dns, host_workdir):
    config = task["config"]
    offliner = config["task_name"]
    container_name = scraper_container_name(task["_id"], offliner)

    # remove container should it exists (should not)
    try:
        docker_client.containers.get(container_name).remove()
    except docker.errors.NotFound:
        pass

    docker_image = docker_client.images.pull(
        config["image"]["name"], tag=config["image"]["tag"]
    )

    # where to mount volume inside scraper
    mount_point = mount_point_for(offliner)

    # mounts will be attached to host's fs, not this one
    mounts = [Mount(str(mount_point), str(host_workdir), type="bind")]

    command = command_for(offliner, config["flags"], mount_point)
    cpu_shares = config["resources"]["cpu"] * DEFAULT_CPU_SHARE
    mem_limit = config["resources"]["memory"]

    return docker_client.containers.run(
        image=docker_image,
        command=command,
        cpu_shares=cpu_shares,
        mem_limit=mem_limit,
        dns=dns,
        detach=True,
        labels={
            "zimscraper": "yes",
            "task_id": task["_id"],
            "tid": short_id(task["_id"]),
            "schedule_id": task["schedule_id"],
            "schedule_name": task["schedule_name"],
        },
        mem_swappiness=0,
        mounts=mounts,
        name=container_name,
        remove=False,  # scaper container will be removed once log&zim handled
    )


def start_task_worker(docker_client, task, webapi_uri, username, workdir, worker_name):
    container_name = task_container_name(task["_id"])

    # remove container should it exists (should not)
    try:
        docker_client.containers.get(container_name).remove()
    except docker.errors.NotFound:
        pass

    image, tag = TASK_WORKER_IMAGE.rsplit(":", 1)
    if tag == "local":
        docker_image = docker_client.images.get(TASK_WORKER_IMAGE)
    else:
        logger.debug(f"pulling image {image}:{tag}")
        docker_image = docker_client.images.pull(image, tag=tag)

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
    return docker_client.containers.run(
        image=docker_image,
        command=command,
        detach=True,
        environment={
            "USERNAME": username,
            "WORKDIR": str(workdir),
            "WEB_API_URI": webapi_uri,
            "WORKER_NAME": worker_name,
        },
        labels={
            "zimtask": "yes",
            "task_id": task["_id"],
            "tid": short_id(task["_id"]),
            "schedule_id": task["schedule_id"],
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
        docker_client.containers.get(container_name).stop(timeout=timeout)
    except docker.errors.NotFound:
        return False
    else:
        return True


def start_uploader(
    docker_client, task, username, host_workdir, upload_dir, filename, move, delete
):
    container_name = upload_container_name(task["_id"], filename)

    # remove container should it exists (should not)
    try:
        docker_client.containers.get(container_name).remove()
    except docker.errors.NotFound:
        pass

    docker_image = docker_client.images.pull("openzim/uploader", tag="latest")

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
    if move:
        command.append("--move")
    if delete:
        command.append("--delete")

    return docker_client.containers.run(
        image=docker_image,
        command=command,
        detach=True,
        environment={"RSA_KEY": str(PRIVATE_KEY)},
        labels={
            "zimuploader": "yes",
            "task_id": task["_id"],
            "tid": short_id(task["_id"]),
            "schedule_id": task["schedule_id"],
            "schedule_name": task["schedule_name"],
            "filename": filename,
        },
        mem_swappiness=0,
        mounts=mounts,
        name=container_name,
        remove=False,  # scaper container will be removed once log&zim handled
    )


def get_container_logs(docker_client, container_name, tail="all"):
    try:
        return (
            docker_client.containers.get(container_name)
            .logs(stdout=True, stderr=True, tail=tail)
            .decode("UTF-8")
        )
    except docker.errors.NotFound:
        return f"Container `{container_name}` gone. Can't get logs"
    except Exception as exc:
        return f"Unable to get logs for `{container_name}`: {exc}"
