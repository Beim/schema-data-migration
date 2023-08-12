import logging
import os

import pytest

from migration import err, helper

from . import testcommon as tc

logger = logging.getLogger(__name__)


def test_integrity_check_for_schema(sort_plan_by_version):
    logger.info("=== start === test_integrity_check_for_schema")
    tc.init_workspace()

    cli = tc.make_schema_migration_plan()

    plan = cli.read_migration_plans().get_latest_plan()
    index_sha1 = plan.change.forward.id
    # break integrity by removing sql file
    sql_files = cli.read_schema_index(index_sha1)
    for sql_sha1, _ in sql_files:
        sql_file_path = helper.sha1_to_path(sql_sha1)
        os.remove(sql_file_path)
        break

    with pytest.raises(err.IntegrityError):
        cli.check_integrity()


def test_integrity_check_for_data(sort_plan_by_version):
    logger.info("=== start === test_integrity_check_for_data")
    tc.init_workspace()

    tc.make_schema_migration_plan()

    plan = tc.make_data_migration_plan(
        "insert into testtable (id, name) values (1, 'foo.bar');",
        "delete from testtable where id = 1;",
    )
    plan.change.forward.sql = ""
    plan.save()

    cli = tc.make_cli({})
    with pytest.raises(err.IntegrityError):
        cli.check_integrity()
