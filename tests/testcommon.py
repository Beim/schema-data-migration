import os
from argparse import Namespace
from typing import Optional, Tuple

from sqlalchemy import text

from migration import migration_plan as mp
from migration.db import db
from migration.env import cli_env
from migration.lib import CLI


def make_args(d: dict) -> Namespace:
    return Namespace(**d)


def make_cli(d: dict = {"environment": "dev"}) -> CLI:
    args = make_args(d)
    return CLI(args=args)


def init_workspace():
    schema = cli_env.UNITTEST_DB_NAME
    sess = db.make_session(
        host=cli_env.UNITTEST_MYSQL_HOST1,
        port=cli_env.UNITTEST_MYSQL_PORT1,
        user="root",
        password=cli_env.MYSQL_PWD,
        schema="mysql",
        echo=False,
        create_all_tables=False,
    )
    sess.execute(text(f"create database if not exists {schema};"))
    sess = db.make_session(
        host=cli_env.UNITTEST_MYSQL_HOST2,
        port=cli_env.UNITTEST_MYSQL_PORT2,
        user="root",
        password=cli_env.MYSQL_PWD,
        schema="mysql",
        echo=False,
        create_all_tables=False,
    )
    sess.execute(text(f"create database if not exists {schema};"))

    cli = make_cli(
        {
            "host": cli_env.UNITTEST_MYSQL_HOST1,
            "port": cli_env.UNITTEST_MYSQL_PORT1,
            "user": "root",
            "schema": schema,
        }
    )
    cli.clean_cwd()
    cli.init()

    # add dev environment
    cli = make_cli(
        {
            "environment": "dev",
            "host": cli_env.UNITTEST_MYSQL_HOST2,
            "port": cli_env.UNITTEST_MYSQL_PORT2,
            "user": "root",
        }
    )
    cli.add_environment()

    # migrate dev environment
    cli = make_cli()
    cli._clear()
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


def make_repeatable_migration_plan(
    name: str = "seed_data",
    forward_sql: str = "insert into testtable (id, name) values (100, 'fooooo')",
    backward_sql: Optional[str] = None,
    dependencies: list = [mp.MigrationSignature(version="0001", name="new_test_table")],
) -> Tuple[CLI, mp.MigrationPlan]:
    cli = CLI(
        args=make_args(
            {
                "name": name,
                "type": "sql",
            }
        )
    )
    cli.make_repeatable_migration()
    repeat_plan: mp.MigrationPlan = cli.read_migration_plans().get_repeatable_plan(name)
    repeat_plan.change.forward.sql = forward_sql
    if backward_sql:
        repeat_plan.change.backward = mp.DataBackward(
            type="sql",
            sql=backward_sql,
        )
    repeat_plan.dependencies = dependencies
    repeat_plan.save()
    return cli, repeat_plan


def make_data_migration_plan(forward_sql: str, backward_sql: str) -> mp.MigrationPlan:
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


def migrate_dev() -> CLI:
    cli = make_cli()
    cli.migrate()
    return cli


def migrate_and_check(len_hists: int, len_row: int):
    cli = migrate_dev()
    check_len_hists_row(cli, len_hists, len_row)


def check_len_hists_row(cli: CLI, len_hists: int, len_row: int):
    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == len_hists
        row = dao.session.execute(text("select name from testtable;")).all()
        assert len(row) == len_row
