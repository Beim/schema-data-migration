import logging
import os
from argparse import Namespace
from typing import List

import pytest
from sqlalchemy import text

from migration import err
from migration import migration_plan as mp
from migration.db import model as dbmodel
from migration.env import cli_env
from migration.lib import CLI, Migrator

logger = logging.getLogger(__name__)

cli_env.ALLOW_UNSAFE = 1


@pytest.fixture
def sort_plan_by_version():
    mp._sort_migration_plans_by = mp.SortAlg.VERSION
    yield
    mp._sort_migration_plans_by = mp._default_sort_migration_plans_by


class FakeMigrator(Migrator):
    def forward(self, migration_plan: mp.MigrationPlan, args: Namespace):
        pass

    def backward(self, migration_plan: mp.MigrationPlan, args: Namespace):
        pass


def make_args(d: dict) -> Namespace:
    return Namespace(**d)


def init_workspace():
    schema = "migration_test"
    args = make_args(
        {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "root",
            "schema": schema,
        }
    )
    cli = CLI(args=args)
    cli.clean_cwd()
    cli.init()

    # add dev environment
    cli = CLI(
        args=make_args(
            {
                "environment": "dev",
                "host": "127.0.0.1",
                "port": 3307,
                "user": "root",
            }
        )
    )
    cli.add_environment()

    # migrate dev environment
    args = make_args(
        {
            "environment": "dev",
        }
    )
    cli = CLI(args=args)
    cli._clear(schema)
    cli.migrate()

    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 1


def make_schema_migration_plan(
    name: str = "new_test_table", id_primary_key: bool = True
) -> CLI:
    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_DIR, "testtable.sql"), "w"
    ) as f:
        if id_primary_key:
            f.write("create table testtable (id int primary key, name varchar(255));")
        else:
            f.write("create table testtable (id int, name varchar(255));")
    args = make_args({"name": name})
    cli = CLI(args=args)
    cli.make_schema_migration()
    return cli


def migrate_dev():
    cli = CLI(
        args=make_args(
            {
                "environment": "dev",
            }
        )
    )
    cli.migrate()
    return cli


def test_migrate_shell_file(sort_plan_by_version):
    logger.info("=== start === test_migrate_shell_file")
    init_workspace()
    make_schema_migration_plan()
    migrate_dev()

    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, "insert.sh"), "w"
    ) as f:
        f.write("""#!/bin/sh
mysql -u$USER -p$MYSQL_PWD -h$HOST -P$PORT -D$SCHEMA \
    -e "insert into testtable (id, name) values (1, 'foo.bar');"
""")
    # add data migration plan
    args = make_args(
        {
            "name": "insert_test_data",
            "type": "shell",
        }
    )
    cli = CLI(args=args)
    cli.make_data_migration()
    data_plan = cli.read_migration_plans().get_plan_by_index(-1)
    data_plan.change.forward.file = "insert.sh"
    data_plan.change.backward = mp.DataBackward(
        type="sql",
        sql="delete from testtable where id = 1;",
    )
    data_plan.save()

    cli = migrate_dev()

    # check migration history
    dao = cli.dao
    with cli.dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 3
        row = dao.session.execute(text("select name from testtable;")).one()
        assert row[0] == "foo.bar"


def test_migrate_python_file(sort_plan_by_version):
    logger.info("=== start === test_migrate_python_file")
    init_workspace()
    make_schema_migration_plan()
    migrate_dev()

    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, "insert.py"), "w"
    ) as f:
        f.write("""from sqlalchemy.orm import Session
from sqlalchemy import text

def run(session: Session):
    with session.begin():
        session.execute(text("insert into testtable (id, name) values (1, 'foo.bar');"))
""")
    # add data migration plan
    args = make_args(
        {
            "name": "insert_test_data",
            "type": "python",
        }
    )
    cli = CLI(args=args)
    cli.make_data_migration()
    data_plan = cli.read_migration_plans().get_plan_by_index(-1)
    data_plan.change.forward.file = "insert.py"
    data_plan.change.backward = mp.DataBackward(
        type="sql",
        sql="delete from testtable where id = 1;",
    )
    data_plan.save()

    cli = migrate_dev()

    # check migration history
    dao = cli.dao
    with cli.dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 3
        row = dao.session.execute(text("select name from testtable;")).one()
        assert row[0] == "foo.bar"


def test_migrate_sql_file(sort_plan_by_version):
    logger.info("=== start === test_migrate_sql_file")
    init_workspace()

    # add schema migration plan
    make_schema_migration_plan()

    # add data migration plan
    args = make_args(
        {
            "name": "insert_test_data",
            "type": "sql_file",
        }
    )
    cli = CLI(args=args)
    cli.make_data_migration()
    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, "insert_test_data.sql"),
        "w",
    ) as f:
        f.write("insert into testtable (id, name) values (1, 'foo.bar');")
    data_plan = cli.read_migration_plans().get_plan_by_index(-1)
    data_plan.change.forward.file = "insert_test_data.sql"
    data_plan.change.backward = mp.DataBackward(
        type="sql",
        sql="delete from testtable where id = 1;",
    )
    data_plan.save()

    # migrate dev environment
    cli = migrate_dev()

    # check migration history
    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 3
        row = dao.session.execute(text("select name from testtable;")).one()
        assert row[0] == "foo.bar"


def make_data_migration_plan(forward_sql: str, backward_sql: str):
    args = make_args(
        {
            "name": "insert_test_data",
            "type": "sql",
        }
    )
    cli = CLI(args=args)
    cli.make_data_migration()
    data_plan = cli.read_migration_plans().get_plan_by_index(-1)
    data_plan.change.forward.sql = forward_sql
    data_plan.change.backward = mp.DataBackward(
        type="sql",
        sql=backward_sql,
    )
    data_plan.save()
    return data_plan


def test_fake_migrate(sort_plan_by_version):
    logger.info("=== start === test_fake_migrate")
    init_workspace()

    make_schema_migration_plan()

    make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )

    args = make_args({"environment": "dev", "fake": True})
    cli = CLI(args=args)
    cli.migrate()

    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 3
        row = dao.session.execute(text("select name from testtable;")).one_or_none()
        assert row is None


def test_fake_rollback(sort_plan_by_version):
    logger.info("=== start === test_fake_rollback")
    init_workspace()

    make_schema_migration_plan()

    make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )

    cli = migrate_dev()

    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 3
        row = dao.session.execute(text("select name from testtable;")).one()
        assert row[0] == "foo.bar"

    args = make_args({"environment": "dev", "fake": True, "version": "0000"})
    cli = CLI(args=args)
    cli.rollback()

    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 1
        row = dao.session.execute(text("select name from testtable;")).one()
        assert row[0] == "foo.bar"


def test_fix_migration(sort_plan_by_version):
    logger.info("=== start === test_fix_migration")
    init_workspace()

    make_data_migration_plan("insert into testtable", "delete from")

    with pytest.raises(Exception):
        # should fail because of invalid sql
        migrate_dev()

    args = make_args({"environment": "dev", "fake": True})
    cli = CLI(args=args)
    cli.fix_migrate()

    dao = cli.dao
    with dao.session.begin():
        hist = dao.get_latest()
        assert hist.state == dbmodel.MigrationState.SUCCESSFUL

    with pytest.raises(Exception):
        args = make_args({"environment": "dev", "version": "0000"})
        cli = CLI(args=args)
        cli.rollback()

    args = make_args({"environment": "dev", "fake": True})
    cli = CLI(args=args)
    cli.fix_rollback()

    dao = cli.dao
    with dao.session.begin():
        hist = dao.get_latest()
        assert hist.ver == "0000"


def test_integrity_check_for_schema(sort_plan_by_version):
    logger.info("=== start === test_integrity_check_for_schema")
    init_workspace()

    cli = make_schema_migration_plan()

    plan = cli.read_migration_plans().get_latest_plan()
    index_sha1 = plan.change.forward.id
    sql_files = cli.read_schema_index(index_sha1)
    for sql_sha1, _ in sql_files:
        sql_file_path = os.path.join(
            cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, sql_sha1[:2], sql_sha1[2:]
        )
        os.remove(sql_file_path)
        break

    with pytest.raises(err.IntegrityError):
        cli.check_integrity()


def test_integrity_check_for_data(sort_plan_by_version):
    logger.info("=== start === test_integrity_check_for_data")
    init_workspace()

    make_schema_migration_plan()

    plan = make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )
    plan.change.forward.sql = ""
    plan.save()

    cli = CLI(args=make_args({}))
    with pytest.raises(err.IntegrityError):
        cli.check_integrity()


def test_clean_schema_store(sort_plan_by_version):
    logger.info("=== start === test_clean_schema_store")
    init_workspace()
    make_schema_migration_plan()
    migrate_dev()

    # write unexpected file to schema store
    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, "foo"), "w"
    ) as f:
        f.write("bar")
    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, "00/11"), "w"
    ) as f:
        f.write("22")

    cli = CLI(
        args=make_args(
            {
                "dry_run": True,
            }
        )
    )
    unexpected_files: List[str] = cli.clean_schema_store()
    assert len(unexpected_files) == 2

    cli = CLI(args=make_args({}))
    unexpected_files: List[str] = cli.clean_schema_store()
    assert len(unexpected_files) == 2
    assert not os.path.exists(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, "foo")
    )
    assert not os.path.exists(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, "00/11")
    )


def test_migrate_happy_flow(sort_plan_by_version):
    logger.info("=== start === test_migrate_happy_flow")
    # init workspace
    init_workspace()

    # add schema migration plan 0001
    make_schema_migration_plan()

    # add data migration plan 0002
    make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )

    # add data migration plan 0003
    make_data_migration_plan(
        "insert into testtable (id, name) values (2, 'foo.baz');",
        "delete from testtable where id = 2;",
    )

    # migrate dev environment
    args = make_args(
        {
            "environment": "dev",
            "version": "2",
        }
    )
    cli = CLI(args=args)
    cli.migrate()

    # check migration history
    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 3
        row = dao.session.execute(
            text("select name from testtable order by id desc limit 1;")
        ).one()
        assert row[0] == "foo.bar"

    # rollback dev environment
    args = make_args(
        {
            "environment": "dev",
            "version": "0",
        }
    )
    cli = CLI(args=args)
    cli.rollback()

    # check migration history
    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 1

    # show migration history
    args = make_args(
        {
            "environment": "dev",
        }
    )
    cli = CLI(args=args)
    is_consistent, len_applied, len_unexpected, len_unapplied = cli.info()
    assert len_applied == 1
    assert len_unexpected == 0
    assert len_unapplied == 3
    assert not is_consistent

    # migrate dev environment
    # it should bring the new table back
    args = make_args(
        {
            "environment": "dev",
        }
    )
    cli = CLI(args=args)
    cli.migrate()

    # check migration history
    dao = cli.dao
    hists = dao.get_all_dto()
    assert len(hists) == 4


def test_repeatable_migration(sort_plan_by_version):
    logger.info("=== start === test_repeatable_migration")

    def migrate_and_check(len_hists: int, len_row: int):
        cli = migrate_dev()
        check(cli, len_hists, len_row)

    def check(cli: CLI, len_hists: int, len_row: int):
        dao = cli.dao
        with dao.session.begin():
            hists = dao.get_all()
            assert len(hists) == len_hists
            row = dao.session.execute(text("select name from testtable;")).all()
            assert len(row) == len_row

    init_workspace()

    # add schema migration plan 0001
    make_schema_migration_plan("new_test_table", id_primary_key=False)

    # add data migration plan 0002
    make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )

    # add repeatable migration plan R_seed_data
    cli = CLI(
        args=make_args(
            {
                "name": "seed_data",
                "type": "sql",
            }
        )
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
    repeat_plan.save()

    # run migrate, should execute the repeatable migration
    migrate_and_check(len_hists=4, len_row=2)

    # run migrate again, should execute the repeatable migration again
    migrate_and_check(len_hists=4, len_row=3)

    # run rollback, should not rollback the repeatable migration
    # the data migration plan should be rolled back
    cli = CLI(
        args=make_args(
            {
                "environment": "dev",
                "version": "0001",
            }
        )
    )
    cli.rollback()
    check(cli=cli, len_hists=3, len_row=2)

    # add schema migration plan 0003
    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_DIR, "testtable.sql"), "w"
    ) as f:
        f.write(
            "create table testtable (id int, addr varchar(255), name varchar(255));"
        )
    args = make_args({"name": "add_addr_to_test_table"})
    cli = CLI(args=args)
    cli.make_schema_migration()
    # set the repeatable migration plan to ignore after this schema migration plan
    repeat_plan: mp.MigrationPlan = cli.read_migration_plans().get_repeatable_plan(
        "seed_data"
    )
    repeat_plan.ignore_after = mp.MigrationSignature(
        version="0003", name="add_addr_to_test_table"
    )
    repeat_plan.save()

    # run migrate, should not execute the repeatable migration
    # len_row = 3 -> two from R_seed_data, one from 0002_insert_test_data
    migrate_and_check(len_hists=5, len_row=3)

    # check info is working
    cli = CLI(
        args=make_args(
            {
                "environment": "dev",
            }
        )
    )
    is_consistent, len_applied, len_unexpected, len_unapplied = cli.info()
    assert is_consistent
    assert len_applied == 4  # TODO let info command support repeatable migration
    assert len_unexpected == 0
    assert len_unapplied == 0
