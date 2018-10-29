import logging
import os
import socket
import sys

import paramiko

from . import errors
from .threading import Thread


class Warehouse:
    logger = logging.getLogger(__name__)

    def __init__(self):
        pass

    def start(self):
        self.logger.info('Welcome to Zimfarm warehouse')

        key = self._get_private_key()
        sock = self._bind_socket()

        while True:
            try:
                client, address = sock.accept()

                self.logger.info('Received incoming connection -- {}:{}'.format(address[0], address[1]))

                thread = Thread(client, key)
                thread.start()
            except Exception as e:
                print("*** Listen/accept failed: " + str(e))

    def _get_private_key(self) -> paramiko.RSAKey:
        try:
            path = os.getenv('RSA_KEY')
            if path is None:
                raise errors.MissingEnvironmentalVariable('RSA_KEY')

            key = paramiko.RSAKey(filename=path)
            self.logger.info('Using private key -- {}'.format(path))
            return key
        except (errors.MissingEnvironmentalVariable, FileNotFoundError, paramiko.SSHException) as e:
            self.logger.error(e)
            sys.exit(1)

    def _bind_socket(self) -> socket.socket:
        try:
            port = os.getenv('PORT', 22)
            if port is None:
                raise errors.MissingEnvironmentalVariable('PORT')
        except errors.MissingEnvironmentalVariable as e:
            self.logger.error(e)
            sys.exit(1)

        try:
            port = int(port)
        except ValueError:
            self.logger.error('Socket binding failed -- {} cannot be converted to integer'.format(port))
            sys.exit(1)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', port))
            sock.listen(10)
            self.logger.info('Listening on port {}'.format(port))
            return sock
        except Exception as e:
            self.logger.error('Socket binding failed -- {}'.format(e))
            sys.exit(1)
