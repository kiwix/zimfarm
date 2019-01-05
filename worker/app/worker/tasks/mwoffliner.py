import docker
import docker.errors

from .base import Base
from ..operations import RunRedis, RunMWOffliner, Upload
from ..utils import Settings


class MWOffliner(Base):
    """MWOffliner zimfarm task. This task have four steps:

    - run redis
    - generate zim file using mwoffliner
    - upload generated zim file

    Steps will be executed one after another.
    """

    name = 'offliner.mwoffliner'

    def run(self, config: dict, warehouse_path: str, tag: str = 'latest'):
        """Run MWOffliner based offliner tasks.

        :param config: offliner config
        :param warehouse_path: path appending to files when uploading
        :param tag: mwoffliner image tag
        :return:
        """

        operations = [
            RunRedis(docker_client=docker.from_env(), container_name=Settings.redis_name),
            RunMWOffliner(docker_client=docker.from_env(), config=config, task_id=self.short_task_id,
                          working_dir_host=Settings.working_dir_host, redis_container_name=Settings.redis_name),
            Upload(warehouse_path, working_dir=Settings.working_dir_container, short_task_id=self.short_task_id)
        ]

        for index, operation in enumerate(operations):
            if isinstance(operation, RunMWOffliner):
                self.logger.info('{name}[{id}] -- Running MWOffliner, mwUrl: {mwUrl}'.format(
                    name=self.name, id=self.short_task_id, mwUrl=config['mwUrl']))
            if isinstance(operation, Upload):
                self.logger.info('{name}[{id}] -- Upload files'.format(name=self.name, id=self.short_task_id))

            try:
                operation.execute()
            except docker.errors.APIError:
                pass
            except docker.errors.ImageNotFound:
                pass
            except docker.errors.ContainerError as error:
                # error.stderr
                pass