import logging

import pytest

from migration.db import model as dbmodel

from . import testcommon as tc

logger = logging.getLogger(__name__)


def test_fix_migration(sort_plan_by_version):
    logger.info("=== start === test_fix_migration")
    tc.init_workspace()

    tc.make_data_migration_plan("insert into testtable", "delete from")

    with pytest.raises(Exception):
        # should fail because of invalid sql
        tc.migrate_dev()

    cli = tc.make_cli({"environment": "dev", "fake": True})
    cli.fix_migrate()

    dao = cli.dao
    with dao.session.begin():
        hist = dao.get_latest()
        assert hist.state == dbmodel.MigrationState.SUCCESSFUL

    with pytest.raises(Exception):
        cli = tc.make_cli({"environment": "dev", "version": "0000"})
        cli.rollback()

    cli = tc.make_cli({"environment": "dev", "fake": True})
    cli.fix_rollback()

    dao = cli.dao
    with dao.session.begin():
        hist = dao.get_latest()
        assert hist.ver == "0000"
