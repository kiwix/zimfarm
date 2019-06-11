from pathlib import Path

from docker import DockerClient
from docker.models.containers import Container

from .base import Operation, ContainerResult

from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

class RunPhet(Operation):
    """Run Phet container with `config`"""

    def __init__(self, docker_client: DockerClient, tag: str, flags: {}, task_id: str, working_dir_host: str, dns: str):
        tag = 'latest' if not tag else tag
        super().__init__()
        self.docker = docker_client
        self.command = self._get_command(flags)
        self.task_id = task_id
        self.working_dir_host = Path(working_dir_host).joinpath(self.task_id).absolute()
        self.image_name = 'openzim/phet:{}'.format(tag)
        self.dns = dns

    def execute(self) -> ContainerResult:
        """Pull and run phet"""

        # pull phet image
        self.docker.images.pull(self.image_name)

        # run phet
        volumes = {self.working_dir_host: {'bind': '/phet/dist', 'mode': 'rw'}}
        container: Container = self.docker.containers.run(
            image=self.image_name, command=self.command, volumes=volumes, detach=True,
            name=f'phet_{self.task_id}', dns=self.dns)

        exit_code = container.wait()['StatusCode']
        stdout = container.logs(stdout=True, stderr=False, tail=100).decode("utf-8")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8")
        result = ContainerResult(self.image_name, self.command, exit_code, stdout, stderr)

        container.remove()

        return result

    @staticmethod
    def _get_command(flags: {}):
        return '/bin/bash -c "cd /phet && npm i && npm start"'
