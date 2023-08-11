"""
    Dummy conftest.py for migration.

    If you don't know what this is for, just leave it empty.
    Read more about conftest.py under:
    - https://docs.pytest.org/en/stable/fixture.html
    - https://docs.pytest.org/en/stable/writing_plugins.html
"""

import pytest

from migration import migration_plan as mp


@pytest.fixture
def sort_plan_by_version():
    mp._sort_migration_plans_by = mp.SortAlg.VERSION
    yield
    mp._sort_migration_plans_by = mp._default_sort_migration_plans_by
