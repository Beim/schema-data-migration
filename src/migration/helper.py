import configparser
import hashlib
import logging
import os
import shlex
import subprocess
from typing import Dict, List

from sqlalchemy.orm import Session

from .db.db import make_session
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


def parse_env_ini() -> configparser.ConfigParser:
    file_path = os.path.join(cli_env.MIGRATION_CWD, cli_env.ENV_INI_FILE)
    with open(file_path) as f:
        data = "[DEFAULT]\n" + f.read()
    config = configparser.ConfigParser()
    config.read_string(data)
    return config


def get_env_ini_section(env: str) -> configparser.SectionProxy:
    cfg = parse_env_ini()
    if not cfg.has_section(env):
        raise Exception(f"Environment [{env}] not found in configuration")
    return cfg[env]


def get_env_with_update(update_env: Dict[str, str]) -> Dict[str, str]:
    os_env = os.environ.copy()
    os_env.update(update_env)
    return os_env


def build_session_from_env(env: str, echo: bool = False) -> Session:
    section = get_env_ini_section(env)
    return make_session(
        host=section["host"],
        port=int(section["port"]),
        user=section["user"],
        password=cli_env.MYSQL_PWD,
        schema=section["schema"],
        echo=echo,
    )


def call_skeema(raw_args: List[str], cwd: str = cli_env.MIGRATION_CWD, env=None):
    # https://stackoverflow.com/questions/39872088/executing-interactive-shell-script-in-python
    cmd = f"{cli_env.SKEEMA_CMD_PATH} " + " ".join(raw_args)
    logger.info("Run %s", cmd)
    subprocess.check_call(shlex.split(cmd), cwd=cwd, env=env)


def files_under_dir(dir_path: str, ends_with: str) -> Dict[str, str]:
    """
    return a map of file name to file path
    """
    res: Dict[str, str] = {}
    for root, _, files in os.walk(dir_path):
        for file in files:
            if not file.endswith(ends_with):
                continue
            res[file] = os.path.join(root, file)
    return res


def check_file_existence(paths: List[str]):
    for path in paths:
        if os.path.exists(path):
            raise Exception(f"{path} already exists")
