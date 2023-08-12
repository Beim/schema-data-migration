import logging
import os

from sqlalchemy import text

from migration import migration_plan as mp
from migration.env import cli_env

from . import testcommon as tc

logger = logging.getLogger(__name__)


def test_migrate_sql_file(sort_plan_by_version):
    logger.info("=== start === test_migrate_sql_file")
    tc.init_workspace()

    # add schema migration plan
    tc.make_schema_migration_plan()

    # add data migration plan
    cli = tc.make_cli(
        {
            "name": "insert_test_data",
            "type": "sql_file",
        }
    )
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
    cli = tc.migrate_dev()

    # check migration history
    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 3
        row = dao.session.execute(text("select name from testtable;")).one()
        assert row[0] == "foo.bar"
