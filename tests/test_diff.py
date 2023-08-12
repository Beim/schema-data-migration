import logging

from . import testcommon as tc
import pytest

logger = logging.getLogger(__name__)

def test_pull(sort_plan_by_version):
    logger.info("=== start === test_pull")

    tc.init_workspace()
    tc.make_schema_migration_plan()
    tc.migrate_dev()

    cli = tc.make_cli({"left": "dev", "right": "dev"})
    cli.diff()

    
    cli = tc.make_cli({"left": "0", "right": "dev"})
    with pytest.raises(Exception):
        cli.diff()


