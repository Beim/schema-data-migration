import logging
import os
from typing import List

from migration.env import cli_env

from . import testcommon as tc

logger = logging.getLogger(__name__)


def test_clean_schema_store(sort_plan_by_version):
    logger.info("=== start === test_clean_schema_store")
    tc.init_workspace()
    tc.make_schema_migration_plan()
    tc.migrate_dev()

    # write unexpected file to schema store
    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, "foo"), "w"
    ) as f:
        f.write("bar")
    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, "00/11"), "w"
    ) as f:
        f.write("22")

    cli = tc.make_cli(
        {
            "dry_run": True,
        }
    )
    unexpected_files: List[str] = cli.clean_schema_store()
    assert len(unexpected_files) == 2

    cli = tc.make_cli({})
    unexpected_files: List[str] = cli.clean_schema_store()
    assert len(unexpected_files) == 2
    assert not os.path.exists(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, "foo")
    )
    assert not os.path.exists(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, "00/11")
    )
