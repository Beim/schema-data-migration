from typing import List

import pytest

from migration import err
from migration import migration_plan as mp


def make_mp(
    sig: mp.MigrationSignature, dependencies: List[mp.MigrationSignature]
) -> mp.MigrationPlan:
    return mp.MigrationPlan(
        version=sig.version,
        name=sig.name,
        dependencies=dependencies,
        author="",
        type=mp.Type.SCHEMA,
        change=mp.Change(forward=mp.SchemaForward(id=""), backward=None),
    )


def make_sigs() -> List[mp.MigrationSignature]:
    return [
        mp.InitialMigrationSignature,
        mp.MigrationSignature(version="0003", name="1"),
        mp.MigrationSignature(version="0002", name="2"),
        mp.MigrationSignature(version="0001", name="3"),
    ]


def test_hash_sig():
    sig_map = {}
    sigs = [
        mp.InitialMigrationSignature,
        mp.MigrationSignature(version="0003", name="1"),
        mp.MigrationSignature(version="0002", name="2"),
        mp.MigrationSignature(version="0001", name="3"),
    ]
    sig_map[sigs[0]] = "0"
    sig_map[sigs[1]] = "1"
    sig_map[sigs[2]] = "2"
    sig_map[sigs[3]] = "3"


def test_sort_migration_plans():
    sigs = make_sigs()
    plans = [
        make_mp(sigs[3], [sigs[2]]),  # 0002 -> 0001
        make_mp(sigs[1], [sigs[0]]),  # 0000 -> 0003
        make_mp(sigs[2], [sigs[1]]),  # 0003 -> 0002
        make_mp(sigs[0], []),
    ]

    expected_plans = [
        make_mp(sigs[0], []),  # 0000
        make_mp(sigs[1], [sigs[0]]),  # 0003
        make_mp(sigs[2], [sigs[1]]),  # 0002
        make_mp(sigs[3], [sigs[2]]),  # 0001
    ]

    sorted_plans = mp.MigrationPlanManager._sort_plans(plans)

    assert sorted_plans == expected_plans


def test_dependency_cycle():
    sigs = make_sigs()
    plans = [
        make_mp(sigs[0], []),
        make_mp(sigs[2], [sigs[1]]),
        make_mp(sigs[1], [sigs[2]]),
    ]

    with pytest.raises(err.IntegrityError):
        mp.MigrationPlanManager._sort_plans(plans)


def test_missing_dependency():
    sigs = make_sigs()
    plans = [
        make_mp(sigs[0], []),
        make_mp(sigs[2], [sigs[1]]),
    ]

    with pytest.raises(err.IntegrityError):
        mp.MigrationPlanManager._sort_plans(plans)


def test_no_initial_migration():
    sigs = make_sigs()
    plans = [
        make_mp(sigs[1], [sigs[0]]),
        make_mp(sigs[2], [sigs[1]]),
    ]

    with pytest.raises(err.IntegrityError):
        mp.MigrationPlanManager._sort_plans(plans)


def test_multi_dependency():
    sigs = make_sigs()
    plans = [
        make_mp(sigs[0], []),
        make_mp(sigs[1], [sigs[0]]),
        make_mp(sigs[2], [sigs[0]]),
    ]

    with pytest.raises(err.IntegrityError):
        mp.MigrationPlanManager._sort_plans(plans)
