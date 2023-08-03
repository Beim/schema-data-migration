import logging
import sys

from migration.env import log_env


def set_log() -> None:
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_env.LOG_FILE)
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        handlers=[handler, file_handler],
        level=logging._nameToLevel.get(log_env.LOG_LEVEL),
        force=True,
    )
