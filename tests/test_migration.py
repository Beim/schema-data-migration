import logging

from sqlalchemy import text

from tests import testcommon as tc

logger = logging.getLogger(__name__)


def test_migrate_happy_flow(sort_plan_by_version):
    logger.info("=== start === test_migrate_happy_flow")
    # init workspace
    tc.init_workspace()

    # add schema migration plan 0001
    tc.make_schema_migration_plan()

    # add data migration plan 0002
    tc.make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )

    # add data migration plan 0003
    tc.make_data_migration_plan(
        "insert into testtable (id, name) values (2, 'foo.baz');",
        "delete from testtable where id = 2;",
    )

    # migrate dev environment
    cli = tc.make_cli(
        {
            "environment": "dev",
            "version": "2",
        }
    )
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
    cli = tc.make_cli(
        {
            "environment": "dev",
            "version": "0",
        }
    )
    cli.rollback()

    # check migration history
    dao = cli.dao
    with dao.session.begin():
        hists = dao.get_all()
        assert len(hists) == 1

    # migrate dev environment
    # it should bring the new table back
    cli = tc.make_cli()
    cli.migrate()

    # check migration history
    dao = cli.dao
    hists = dao.get_all_dto()
    assert len(hists) == 4
