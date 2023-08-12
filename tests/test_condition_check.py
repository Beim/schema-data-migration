import logging
import os

import pytest

from migration import err
from migration import migration_plan as mp
from migration.db import model as dbmodel
from migration.env import cli_env
from tests import testcommon as tc

logger = logging.getLogger(__name__)


def test_condition_check_sql(sort_plan_by_version):
    logger.info("=== start === test_condition_check_sql")
    tc.init_workspace()
    # add schema migration plan 0001
    tc.make_schema_migration_plan()
    # add data migration plan 0002
    data_plan = tc.make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )
    # this check should prevent the data migration plan from being applied
    data_plan.change.forward.precheck = mp.ConditionCheck(
        type=str(mp.DataChangeType.SQL),
        sql="select count(*) from testtable where id = 1;",
        expected=1,
    )
    data_plan.save()

    with pytest.raises(err.ConditionCheckFailedError):
        cli = tc.migrate_dev()

    cli = tc.make_cli({"environment": "dev"})
    cli.build_dao()
    hists = cli.dao.get_all_dto()
    assert len(hists) == 3
    assert hists[-1].state == dbmodel.MigrationState.PROCESSING


def test_condition_check_sql_file(sort_plan_by_version):
    logger.info("=== start === test_condition_check_sql_file")
    tc.init_workspace()
    tc.make_schema_migration_plan()
    data_plan = tc.make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )
    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, "check.sql"), "w"
    ) as f:
        f.write("select count(*) from testtable where id = 1;")
    data_plan.change.forward.precheck = mp.ConditionCheck(
        type=str(mp.DataChangeType.SQL_FILE),
        file="check.sql",
        expected=1,
    )
    data_plan.save()

    with pytest.raises(err.ConditionCheckFailedError):
        cli = tc.migrate_dev()

    cli = tc.make_cli()
    cli.build_dao()
    hists = cli.dao.get_all_dto()
    assert len(hists) == 3
    assert hists[-1].state == dbmodel.MigrationState.PROCESSING


@pytest.mark.slow
def test_condition_check_typescript_file(sort_plan_by_version):
    logger.info("=== start === test_condition_check_typescript_file")
    tc.init_workspace()

    # add schema migration plan 0001
    tc.make_schema_migration_plan()

    # add data migration plan 0002
    cli = tc.make_cli(
        {
            "name": "insert_test_data",
            "type": mp.DataChangeType.TYPESCRIPT,
        }
    )
    cli.make_data_migration()
    data_plan = cli.read_migration_plans().get_plan_by_index(-1)

    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, "run.ts"), "w"
    ) as f:
        f.write("""import { Column, PrimaryColumn, Entity, DataSource } from "typeorm"
@Entity()
class Testtable {
  @PrimaryColumn()
  id: number

  @Column()
  name: string
}

export const Entities = [Testtable]

export const Run = async (datasource: DataSource, args: { [key: string]: string }): Promise<number> => {
    await datasource.manager.insert(Testtable, { id: 1, name: "fooxxx" })
    return 0
}
""")  # noqa
    data_plan.change.forward.file = "run.ts"

    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, "check.ts"), "w"
    ) as f:
        f.write("""import { Column, PrimaryColumn, Entity, DataSource } from "typeorm"
@Entity()
class Testtable {
  @PrimaryColumn()
  id: number

  @Column()
  name: string
}

export const Entities = [Testtable]

export const Run = async (datasource: DataSource, args: { [key: string]: string }): Promise<number> => {
    const count = await datasource.manager.count(Testtable, { where: { id: 1 } })
    return count
}
""")  # noqa
    data_plan.change.forward.precheck = mp.ConditionCheck(
        type=str(mp.DataChangeType.TYPESCRIPT),
        file="check.ts",
        expected=1,
    )
    data_plan.save()

    import subprocess

    subprocess.run(["npm", "install"], cwd=cli_env.MIGRATION_CWD)
    with pytest.raises(err.ConditionCheckFailedError):
        cli = tc.migrate_dev()

    cli = tc.make_cli()
    cli.build_dao()
    hists = cli.dao.get_all_dto()
    assert len(hists) == 3
    assert hists[-1].state == dbmodel.MigrationState.PROCESSING

    # fix the expected value, and fix migration
    data_plan.change.forward.precheck.expected = 0
    data_plan.save()
    cli = tc.make_cli()
    cli.fix_migrate()

    cli = tc.make_cli()
    cli.build_dao()
    hists = cli.dao.get_all_dto()
    assert len(hists) == 3
    assert hists[-1].state == dbmodel.MigrationState.SUCCESSFUL


def test_condition_check_shell_file(sort_plan_by_version):
    logger.info("=== start === test_condition_check_shell_file")
    tc.init_workspace()
    tc.make_schema_migration_plan()
    tc.migrate_dev()

    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, "check.sh"), "w"
    ) as f:
        f.write("""#!/bin/sh
result=$(mysql -uroot -h127.0.0.1 -P3307 -Dmigration_test -p's@mplep@ssword' -e "select count(*) from testtable;" | awk 'NR==2{print $1}')
if [ -n "$result" ] && [ "$result" -eq "$SDM_EXPECTED" ]; then
    exit 0
else
    exit 1
fi
""")  # noqa
    # add data migration plan
    data_plan = tc.make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )
    data_plan.change.forward.precheck = mp.ConditionCheck(
        type=str(mp.DataChangeType.SHELL),
        file="check.sh",
        expected=1,
    )
    data_plan.save()

    with pytest.raises(err.ConditionCheckFailedError):
        tc.migrate_dev()

    cli = tc.make_cli()
    cli.build_dao()
    hists = cli.dao.get_all_dto()
    assert len(hists) == 3
    assert hists[-1].state == dbmodel.MigrationState.PROCESSING

    # fix the expected value, and fix migration
    data_plan.change.forward.precheck.expected = 0
    data_plan.save()
    cli = tc.make_cli()
    cli.fix_migrate()
    cli = tc.make_cli()
    cli.build_dao()
    hists = cli.dao.get_all_dto()
    assert len(hists) == 3
    assert hists[-1].state == dbmodel.MigrationState.SUCCESSFUL


def test_condition_check_python_file(sort_plan_by_version):
    logger.info("=== start === test_condition_check_python_file")
    tc.init_workspace()
    tc.make_schema_migration_plan()
    data_plan = tc.make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )
    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, "check.py"), "w"
    ) as f:
        f.write("""from sqlalchemy.orm import Session
from sqlalchemy import text

def run(session: Session, args: dict) -> int:
    with session.begin():
        result = session.execute(text("select count(*) from testtable where id = 1;")).one_or_none()
        return result[0]
""")  # noqa
    data_plan.change.forward.precheck = mp.ConditionCheck(
        type=str(mp.DataChangeType.PYTHON),
        file="check.py",
        expected=1,
    )
    data_plan.save()

    with pytest.raises(err.ConditionCheckFailedError):
        cli = tc.migrate_dev()

    cli = tc.make_cli()
    cli.build_dao()
    hists = cli.dao.get_all_dto()
    assert len(hists) == 3
    assert hists[-1].state == dbmodel.MigrationState.PROCESSING

    # fix migration plan, and retry to fix migration
    data_plan.change.forward.precheck.expected = 0
    data_plan.save()
    cli = tc.make_cli()
    cli.fix_migrate()
    hists = cli.dao.get_all_dto()
    assert len(hists) == 3
    assert hists[-1].state == dbmodel.MigrationState.SUCCESSFUL
