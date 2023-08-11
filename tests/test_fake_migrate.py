import logging

from sqlalchemy import text

from migration import migration_plan as mp
from migration.lib import CLI
from tests import testcommon as tc

logger = logging.getLogger(__name__)


def test_fake_migrate(sort_plan_by_version):
    logger.info("=== start === test_fake_migrate")
    tc.init_workspace()
    tc.make_schema_migration_plan(name="new_test_table", id_primary_key=False)
    tc.make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )
    # in fake mode, the repeatable migration plan will not be executed
    # and it will not be recorded in the history table
    tc.make_repeatable_migration_plan(
        name="seed_data",
        forward_sql="insert into testtable (id, name) values (100, 'fooooo')",
        dependencies=[mp.MigrationSignature(version="0001", name="new_test_table")],
    )

    cli = tc.make_cli({"environment": "dev", "fake": True})
    cli.migrate()

    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        # init + new_test_table + insert_test_data
        assert len(hists) == 3
        row = dao.session.execute(text("select name from testtable;")).one_or_none()
        assert row is None


def test_fake_rollback(sort_plan_by_version):
    logger.info("=== start === test_fake_rollback")
    tc.init_workspace()
    tc.make_schema_migration_plan()
    tc.make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )
    # the repeatable migration plan will be rolled back in fake mode
    tc.make_repeatable_migration_plan(
        name="seed_data",
        forward_sql="insert into testtable (id, name) values (100, 'fooooo')",
        dependencies=[mp.MigrationSignature(version="0001", name="new_test_table")],
    )
    cli = tc.migrate_dev()

    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 4
        row = dao.session.execute(text("select name from testtable;")).first()
        assert row[0] == "foo.bar"

    args = tc.make_args({"environment": "dev", "fake": True, "version": "0000"})
    cli = CLI(args=args)
    cli.rollback()

    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 1
        row = dao.session.execute(text("select name from testtable;")).first()
        assert row[0] == "foo.bar"
