import logging
import os
from typing import List

from migration.env import cli_env

from . import testcommon as tc

logger = logging.getLogger(__name__)


def list_files(d: str, suffix: str = ".sql") -> List[str]:
    res: List[str] = []
    for root, dirs, files in os.walk(cli_env.SDM_SCHEMA_DIR):
        for file in files:
            if file.endswith(suffix):
                res.append(os.path.join(root, file))
    return res


def test_pull(sort_plan_by_version):
    logger.info("=== start === test_pull")

    tc.init_workspace()
    tc.make_schema_migration_plan()
    tc.migrate_dev()

    # pull by env
    for f in list_files(cli_env.SDM_SCHEMA_DIR, ".sql"):
        os.remove(f)

    cli = tc.make_cli({"env_or_version": "dev"})
    cli.pull()

    assert len(list_files(cli_env.SDM_SCHEMA_DIR, ".sql")) == 1

    # pull by version
    for f in list_files(cli_env.SDM_SCHEMA_DIR, ".sql"):
        os.remove(f)

    cli = tc.make_cli({"env_or_version": "0001"})
    cli.pull()

    assert len(list_files(cli_env.SDM_SCHEMA_DIR, ".sql")) == 1
