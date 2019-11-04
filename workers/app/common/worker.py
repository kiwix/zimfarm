#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import os
import sys
import pathlib
import datetime

import docker
import requests

from common import logger
from common.constants import AUTH_EXPIRY, DOCKER_SOCKET, PRIVATE_KEY
from common.dispatcher import get_token_ssh, query_api


class BaseWorker:

    def print_config(self, **kwargs):
        # log configuration values
        config_str = "configuration:"
        for key, value in kwargs.items():
            setattr(self, key, value)
            if key == "password":
                continue
            config_str += f"\n\t{key}={value}"
        logger.info(config_str)

    def check_workdir(self):
        self.workdir = pathlib.Path(self.workdir).resolve()
        logger.info(f"testing workdir at {self.workdir}…")
        if (
            not self.workdir.exists()
            or not self.workdir.is_dir()
            or not os.access(self.workdir, os.W_OK)
        ):
            logger.critical(f"\tworkdir is not a writable path")
            sys.exit(1)
        else:
            logger.info("\tworkdir is available and writable")

    def check_private_key(self):
        logger.info(f"testing private key at {PRIVATE_KEY}…")
        if (
            not PRIVATE_KEY.exists()
            or not PRIVATE_KEY.is_file()
            or not os.access(PRIVATE_KEY, os.R_OK)
        ):
            logger.critical(f"\tprivate key is not a readable path")
            sys.exit(1)
        else:
            logger.info("\tprivate key is available and readable")

    def check_auth(self):
        logger.debug("check_auth()")
        self.access_token = self.refresh_token = None
        self.authenticated_on = datetime.datetime(2019, 1, 1)

        logger.info(f"testing authentication with {self.webapi_uri}…")
        success, status_code, response = self.query_api(
            "GET", "/users/", params={"limit": 1}
        )
        if success and "items" in response and "meta" in response:
            logger.info("\tauthentication successful")
        else:
            logger.critical("\tauthentication failed.")
            sys.exit(1)

    def check_docker(self):

        logger.info(f"testing docker API on {DOCKER_SOCKET}…")
        if (
            not DOCKER_SOCKET.exists()
            or not DOCKER_SOCKET.is_socket()
            or not os.access(DOCKER_SOCKET, os.R_OK)
        ):
            logger.critical(f"\tsocket ({DOCKER_SOCKET}) not available.")
            sys.exit(1)
        self.docker = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET}")
        try:
            if len(self.docker.containers.list(all=False)) < 1:
                logger.warning("\tno running container, am I out-of-docker?")
        except Exception as exc:
            logger.critical("\tdocker API access failed: exiting.")
            logger.exception(exc)
            sys.exit(1)
        else:
            logger.info("\tdocker API access successful")
            # self.docker_api = docker.APIClient(base_url=f"unix://{DOCKER_SOCKET}")

    def authenticate(self, force=False):
        # our access token should grant us access for 60mn
        if force or (
            self.authenticated_on + datetime.timedelta(AUTH_EXPIRY)
            <= datetime.datetime.now()
        ):
            try:
                self.access_token, self.refresh_token = get_token_ssh(
                    self.webapi_uri, self.username, PRIVATE_KEY
                )
                self.authenticated_on = datetime.datetime.now()
                return True
            except Exception as exc:
                logger.error(f"authenticate() failure: {exc}")
                logger.exception(exc)
            return False
        return True

    def query_api(self, method, path, payload=None, params=None, headers={}):
        if not self.authenticate():
            return

        attempts = 0
        while attempts <= 1:
            success, status_code, response = query_api(
                self.access_token,
                method,
                f"{self.webapi_uri}{path}",
                payload,
                params,
                headers,
            )
            attempts += 1

            # Unauthorised error: attempt to re-auth as scheduler might have restarted?
            if status_code == requests.codes.UNAUTHORIZED:
                self.authenticate(force=True)
                continue
            else:
                break

        return success, status_code, response