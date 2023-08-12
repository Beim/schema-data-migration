import logging
import os

import pytest

from migration import err
from migration import migration_plan as mp
from migration.env import cli_env
from tests import testcommon as tc

logger = logging.getLogger(__name__)


def test_condition_check_repeatable_migration(sort_plan_by_version):
    logger.info("=== start === test_condition_check_repeatable_migration")
    tc.init_workspace()
    # add schema migration plan 0001
    tc.make_schema_migration_plan("new_test_table", id_primary_key=False)
    tc.migrate_dev()
    # add data migration plan 0002
    tc.make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )

    # add repeatable migration plan R_seed_data
    cli = tc.make_cli(
        {
            "name": "seed_data",
            "type": "sql",
        }
    )
    cli.make_repeatable_migration()
    repeat_plan: mp.MigrationPlan = cli.read_migration_plans().get_repeatable_plan(
        "seed_data"
    )
    repeat_plan.change.forward.sql = (
        "insert into testtable (id, name) values (100, 'foooooo');"
    )
    repeat_plan.dependencies = [
        mp.MigrationSignature(version="0001", name="new_test_table"),
    ]
    repeat_plan.change.forward.precheck = mp.ConditionCheck(
        type=str(mp.DataChangeType.PYTHON),
        file="check.py",
        expected=0,
    )
    repeat_plan.save()
    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, "check.py"), "w"
    ) as f:
        f.write("""from sqlalchemy.orm import Session
from sqlalchemy import text

def run(session: Session, args: dict) -> int:
    print("SDM_CHECKSUM_MATCH equals to {}".format(args['SDM_CHECKSUM_MATCH']))
    return int(args['SDM_CHECKSUM_MATCH'])
""")

    # run migrate, should execute the repeatable migration
    tc.migrate_and_check(len_hists=4, len_row=2)

    # run migrate again, should not execute the repeatable migration again
    #   because the checksum validation in python file failed
    with pytest.raises(err.ConditionCheckFailedError):
        tc.migrate_dev()
    cli = tc.make_cli()
    cli.build_dao()
    tc.check_len_hists_row(cli, len_hists=4, len_row=2)


def test_repeatable_migration(sort_plan_by_version):
    logger.info("=== start === test_repeatable_migration")
    tc.init_workspace()
    # add schema migration plan 0001
    tc.make_schema_migration_plan("new_test_table", id_primary_key=False)
    # add data migration plan 0002
    tc.make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )

    _, repeat_plan = tc.make_repeatable_migration_plan(
        name="seed_data",
        forward_sql="insert into testtable (id, name) values (100, 'foooooo');",
        dependencies=[mp.MigrationSignature(version="0001", name="new_test_table")],
    )

    # run migrate, should execute the repeatable migration
    tc.migrate_and_check(len_hists=4, len_row=2)

    # run migrate again, should not execute the repeatable migration again
    #   because the checksum is the same
    tc.migrate_and_check(len_hists=4, len_row=2)

    repeat_plan.change.forward.sql = (
        "insert into testtable (id, name) values (100, 'barrrrrrrrr');"
    )
    repeat_plan.save()

    # run migrate, should execute the repeatable migration
    #   because the checksum is different
    tc.migrate_and_check(len_hists=4, len_row=3)

    # run rollback, should not rollback the repeatable migration
    # the data migration plan should be rolled back
    # because it's dependency 0001 still exists
    cli = tc.make_cli(
        {
            "environment": "dev",
            "version": "0001",
        }
    )
    cli.rollback()
    tc.check_len_hists_row(cli=cli, len_hists=3, len_row=2)

    # add schema migration plan 0003 which alter the table
    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_DIR, "testtable.sql"), "w"
    ) as f:
        f.write(
            "create table testtable (id int, addr varchar(255), name varchar(255));"
        )
    cli = tc.make_cli({"name": "add_addr_to_test_table"})
    cli.make_schema_migration()
    # set the repeatable migration plan to ignore after this schema migration plan
    repeat_plan: mp.MigrationPlan = cli.read_migration_plans().get_repeatable_plan(
        "seed_data"
    )
    repeat_plan.ignore_after = mp.MigrationSignature(
        version="0003", name="add_addr_to_test_table"
    )
    repeat_plan.save()

    # run migrate, should not execute the repeatable migration because it's ignored
    # len_row = 3 -> two from R_seed_data, one from 0002_insert_test_data
    tc.migrate_and_check(len_hists=5, len_row=3)

    # check info is working
    cli = tc.make_cli()
    _, len_applied = cli.info()
    assert len_applied == 5

    # add new repeatable migration plan R_seed_addr_data
    tc.make_repeatable_migration_plan(
        name="seed_addr_data",
        forward_sql=(
            "insert into testtable (id, addr, name) values (200, 'Mars', 'foooooo');"
        ),
        backward_sql="delete from testtable where id = 200;",
        dependencies=[
            mp.MigrationSignature(version="0003", name="add_addr_to_test_table")
        ],
    )

    # run migrate, should execute the repeatable migration
    tc.migrate_and_check(len_hists=6, len_row=4)

    # run rollback to 0002, should rollback the repeatable migration seed_addr_data
    # because it depends on the schema migration plan 0003_add_addr_to_test_table
    cli = tc.make_cli(
        {
            "environment": "dev",
            "version": "0002",
        }
    )
    cli.rollback()
    tc.check_len_hists_row(cli=cli, len_hists=4, len_row=3)
