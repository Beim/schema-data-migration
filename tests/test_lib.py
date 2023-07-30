import os
from argparse import Namespace

import pytest
from sqlalchemy import text

from migration import err
from migration import migration_plan as mp
from migration.db import model as dbmodel
from migration.env import cli_env
from migration.lib import CLI, Migrator

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


def make_schema_migration_plan() -> CLI:
    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_DIR, "testtable.sql"), "w"
    ) as f:
        f.write("create table testtable (id int primary key, name varchar(255));")
    args = make_args({"name": "new_test_table"})
    cli = CLI(args=args)
    cli.make_schema_migration()
    return cli


def migrate_dev():
    args = make_args(
        {
            "environment": "dev",
        }
    )
    cli = CLI(args=args)
    cli.migrate()
    return cli


def test_migrate_shell_file(sort_plan_by_version):
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
    data_plan.change.forward.shell_file = "insert.sh"
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
    data_plan.change.forward.python_file = "insert.py"
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
    data_plan.change.forward.sql_file = "insert_test_data.sql"
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


def test_migrate(sort_plan_by_version):
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
    info = cli.info()
    assert len(info) == 4  # it should contain unapplied migration plans

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
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 4
