import logging
import sys

from migration.context import context_var
from migration.env import log_env


class MyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.log_id = context_var.get_request_id()
        return True


def set_log() -> None:
    formatter = logging.Formatter(
        # "%(asctime)s|%(levelname)s|%(log_id)s|%(process)d"
        # "%(asctime)s|%(levelname)s|%(process)d|%(module)s:%(lineno)d|%(message)s"
        "%(asctime)s [%(levelname)s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    filter = MyFilter()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(filter)
    logging.basicConfig(
        handlers=[handler],
        level=logging._nameToLevel.get(log_env.LOG_LEVEL),
        force=True,
    )
