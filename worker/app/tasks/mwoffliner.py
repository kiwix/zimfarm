import logging
import shutil
from pathlib import Path

import docker
import docker.errors

from operations import RunRedis, RunMWOffliner, Upload
from operations.base import OfflinerError, UploadError
from utils import Settings
from .base import Base

logger = logging.getLogger(__name__)


class MWOffliner(Base):
    """MWOffliner zimfarm task. This task have four steps:

    - run redis
    - generate zim file using mwoffliner
    - upload generated zim file

    Steps will be executed one after another.
    """

    name = 'offliner.mwoffliner'

    def run(self, flags: dict, image: dict, warehouse_path: str, *args, **kwargs):
        """Run MWOffliner based offliner tasks.

        :param flags: offliner flags
        :param image: offliner image name and tag
        :param warehouse_path: path appending to files when uploading
        :return:
        """

        image_tag = image.get('tag', 'latest')
        working_dir_container = Path(Settings.working_dir_container).joinpath(self.task_id)

        try:
            # run redis
            run_redis = RunRedis(docker_client=docker.from_env(), container_name=Settings.redis_name)
            run_redis.execute()

            # run mwoffliner
            run_mwoffliner = RunMWOffliner(
                docker_client=docker.from_env(), tag=image_tag, flags=flags,
                task_id=self.task_id, working_dir_host=Settings.working_dir_host,
                redis_container_name=Settings.redis_name)
            self.logger.info('{name}[{id}] -- Running MWOffliner, mwUrl: {mwUrl}'.format(
                name=self.name, id=self.task_id, mwUrl=flags['mwUrl']))
            self.logger.debug('{name}[{id}] -- Running MWOffliner, command: {command}'.format(
                name=self.name, id=self.task_id, command=run_mwoffliner.command))
            offliner_stdout = run_mwoffliner.execute()
            self.send_event('offliner_finished', stdout=offliner_stdout)

            # upload files
            upload = Upload(remote_working_dir=warehouse_path, working_dir=working_dir_container)
            self.logger.info('{name}[{id}] -- Upload files'.format(name=self.name, id=self.task_id))
            upload.execute()

            stats = self.get_file_stats(working_dir_container)
            self.clean_up(working_dir_container)
            return stats
        except OfflinerError as e:
            self.clean_up(working_dir_container)
            self.send_event('offliner_failed', exception=e)
            raise e
        except UploadError as e:
            self.clean_up(working_dir_container)
            self.send_event('upload_failed', exception=e)
            raise e

    @staticmethod
    def get_file_stats(working_dir: Path):
        stats = []
        for file in working_dir.iterdir():
            if file.is_dir():
                continue
            stats.append({'name': file.name, 'size': file.stat().st_size})
        return stats

    @staticmethod
    def clean_up(working_dir: Path):
        shutil.rmtree(working_dir)
