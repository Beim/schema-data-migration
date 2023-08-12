import logging
import os

from sqlalchemy import text

from migration import migration_plan as mp
from migration.env import cli_env
from tests import testcommon as tc

logger = logging.getLogger(__name__)


def test_migrate_shell_file(sort_plan_by_version):
    logger.info("=== start === test_migrate_shell_file")
    tc.init_workspace()
    tc.make_schema_migration_plan()
    tc.migrate_dev()

    with open(
        os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, "insert.sh"), "w"
    ) as f:
        f.write("""#!/bin/sh
mysql -u$USER -p$MYSQL_PWD -h$HOST -P$PORT -D$SCHEMA \
    -e "insert into testtable (id, name) values (1, 'foo.bar');"
""")
    # add data migration plan
    cli = tc.make_cli(
        {
            "name": "insert_test_data",
            "type": "shell",
        }
    )
    cli.make_data_migration()
    data_plan = cli.read_migration_plans().get_plan_by_index(-1)
    data_plan.change.forward.file = "insert.sh"
    data_plan.change.backward = mp.DataBackward(
        type="sql",
        sql="delete from testtable where id = 1;",
    )
    data_plan.save()

    cli = tc.migrate_dev()

    # check migration history
    dao = cli.dao
    with cli.dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 3
        row = dao.session.execute(text("select name from testtable;")).one()
        assert row[0] == "foo.bar"
