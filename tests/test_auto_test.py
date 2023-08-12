import logging
import os

from migration import consts

from . import testcommon as tc

logger = logging.getLogger(__name__)


def test_auto_test(sort_plan_by_version):
    logger.info("=== start === test_auto_test")
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

    for t in consts.ALL_GEN_TEST_TYPE:
        cli = tc.make_cli({"type": t, "output": "test_plan.json"})
        cli.test_gen()

        cli = tc.make_cli(
            {
                "input": "test_plan.json",
                "environment": "dev",
                "clear": True,
                "type": t,
                "walk_len": 10,
                "start": "0001",
                "important": "0002",
                "non_important": "0003",
            }
        )
        cli.test_run()
    os.remove("test_plan.json")
