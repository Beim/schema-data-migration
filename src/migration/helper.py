import hashlib
import logging
import os
from typing import List

from .env import cli_env

logger = logging.getLogger(__name__)


class SHA1Helper:
    def __init__(self):
        self.sha1 = hashlib.sha1()

    def update_str(self, str_list: List[str]):
        for s in str_list:
            self.sha1.update(s.encode())

    def update_file(self, file_list: List[str]):
        for file in file_list:
            with open(file, "r") as f:
                data = f.read()
            self.sha1.update(data.encode())

    def hexdigest(self) -> str:
        return self.sha1.hexdigest()


def sha1_encode(str_list: List[str]):
    # create a SHA1 hash object
    sha1 = hashlib.sha1()
    # update the hash object with the string
    for s in str_list:
        sha1.update(s.encode())
    # get the hexadecimal representation of the hash
    hex_digest = sha1.hexdigest()
    return hex_digest


def sha1_to_path(sha1: str) -> str:
    return os.path.join(
        cli_env.MIGRATION_CWD,
        cli_env.SCHEMA_STORE_DIR,
        sha1[:2],
        sha1[2:],
    )


def write_sha1_file(sha1: str, content: str):
    folder = os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, sha1[:2])
    filename = sha1[2:]
    # if file exist, return directly, otherwise write file
    filepath = os.path.join(folder, filename)
    logger.debug("Wrote schema store file to %s", filepath)
    if os.path.exists(filepath):
        return
    with open(filepath, "w") as f:
        f.write(content)


def truncate_str(s: str, max_len: int = 40) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."
