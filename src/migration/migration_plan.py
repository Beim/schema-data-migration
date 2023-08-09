import json
import logging
import os
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Dict, List, Optional, Tuple

import dacite
import networkx as nx

from migration import err
from migration.env import cli_env

from . import helper

logger = logging.getLogger(__name__)


class Type(StrEnum):
    SCHEMA = "schema"
    DATA = "data"
    REPEATABLE = "repeatable"


VERSIONED_TYPES = [Type.SCHEMA, Type.DATA]


class DataChangeType(StrEnum):
    SQL = "sql"
    SQL_FILE = "sql_file"
    PYTHON = "python"
    SHELL = "shell"
    TYPESCRIPT = "typescript"

    @classmethod
    def is_valid(cls, x):
        return (
            x == cls.SQL
            or x == cls.SQL_FILE
            or x == cls.PYTHON
            or x == cls.SHELL
            or x == cls.TYPESCRIPT
        )


@dataclass
class ConditionCheck:
    type: str  # DataChangeType
    sql: Optional[str | None] = None
    file: Optional[str | None] = None
    expected: Optional[int | None] = None

    def to_dict(self) -> Dict:
        obj = {
            "type": self.type,
        }
        match self.type:
            case DataChangeType.SQL:
                obj["sql"] = self.sql
            case (
                DataChangeType.SQL_FILE
                | DataChangeType.PYTHON
                | DataChangeType.SHELL
                | DataChangeType.TYPESCRIPT
            ):
                obj["file"] = self.file
        if self.expected is not None:
            obj["expected"] = self.expected
        return obj


@dataclass
class SchemaForward:
    id: str
    precheck: Optional[ConditionCheck | None] = None
    postcheck: Optional[ConditionCheck | None] = None

    def to_str_for_print(self) -> str:
        return self.id

    def to_dict(self) -> Dict:
        obj = {
            "id": self.id,
        }
        if self.precheck is not None:
            obj["precheck"] = self.precheck.to_dict()
        if self.postcheck is not None:
            obj["postcheck"] = self.postcheck.to_dict()
        return obj


@dataclass
class DataForward:
    type: str  # DataChangeType
    sql: Optional[str | None] = None
    file: Optional[str | None] = None
    precheck: Optional[ConditionCheck | None] = None
    postcheck: Optional[ConditionCheck | None] = None

    def to_dict(self) -> Dict:
        obj = {
            "type": self.type,
        }
        match self.type:
            case DataChangeType.SQL:
                obj["sql"] = self.sql
            case (
                DataChangeType.SQL_FILE
                | DataChangeType.PYTHON
                | DataChangeType.SHELL
                | DataChangeType.TYPESCRIPT
            ):
                obj["file"] = self.file
        if self.precheck is not None:
            obj["precheck"] = self.precheck.to_dict()
        if self.postcheck is not None:
            obj["postcheck"] = self.postcheck.to_dict()
        return obj

    def to_str_for_print(self) -> str:
        if self.type == DataChangeType.SQL:
            # to match the length if index sha1
            return helper.truncate_str(self.sql, max_len=40)
        elif (
            self.type == DataChangeType.SQL_FILE
            or self.type == DataChangeType.PYTHON
            or self.type == DataChangeType.SHELL
            or self.type == DataChangeType.TYPESCRIPT
        ):
            return self.file
        else:
            raise Exception(f"Invalid type {self.type}")


@dataclass
class SchemaBackward(SchemaForward):
    pass


@dataclass
class DataBackward(DataForward):
    pass


@dataclass
class Change:
    forward: Optional[SchemaForward | DataForward]
    backward: Optional[SchemaBackward | DataBackward | None]

    def to_dict(self):
        obj = {
            "forward": self.forward.to_dict(),
        }
        if self.backward is not None:
            obj["backward"] = self.backward.to_dict()
        return obj


@dataclass
class MigrationSignature:
    version: str
    name: Optional[str] = None

    def __hash__(self) -> int:
        return hash((self.version, self.name))

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, MigrationSignature):
            return False
        return self.version == o.version and self.name == o.name

    def __str__(self) -> str:
        return f"{self.version}_{self.name}"

    def to_dict(self) -> Dict:
        obj = {
            "version": self.version,
        }
        if self.name is not None:
            obj["name"] = self.name
        return obj

    @staticmethod
    def from_str(s: str) -> "MigrationSignature":
        split = s.split("_")
        if len(split) < 1:
            raise Exception(f"Invalid version or name {s}")
        version = split[0].zfill(4)
        name = "_".join(split[1:])
        if not name:
            name = None
        sig = MigrationSignature(version=version, name=name)
        sig.validate(type=None, require_name=False)
        return sig

    def validate(self, type: Type = None, require_name: bool = True):
        # validate version
        match type:
            case Type.SCHEMA | Type.DATA:
                if not self.version.isdigit() or int(self.version) < 0:
                    raise Exception(f"Invalid version {self.version}")
            case Type.REPEATABLE:
                if self.version != RepeatableVersion:
                    raise Exception(f"Invalid version {self.version}")
            case None:
                if self.version.isdigit():
                    if int(self.version) < 0:
                        raise Exception(f"Invalid version {self.version}")
                else:
                    if self.version != RepeatableVersion:
                        raise Exception(f"Invalid version {self.version}")
            case _:
                raise Exception(f"Invalid type {self.type}")
        # validate name
        if self.name is None and not require_name:
            return
        if not re.match(r"^[a-zA-Z0-9_]+$", self.name):
            raise Exception(
                f"Invalid name {self.name}, only alphanumeric and _ allowed"
            )


InitialMigrationSignature = MigrationSignature(version="0000", name="init")
RepeatableVersion = "R"


@dataclass
class MigrationPlan:
    version: str
    name: str
    author: str
    type: Optional[Type | str]
    change: Change
    dependencies: List[MigrationSignature]
    ignore_after: Optional[MigrationSignature | None] = None

    _checksum: Optional[str | None] = None  # the value is not saved to file
    _checksum_match: Optional[bool | None] = None  # the value is not saved to file

    def set_checksum_match(self, checksum_match: bool):
        self._checksum_match = checksum_match

    def get_checksum_match(self) -> Optional[bool | None]:
        return self._checksum_match

    def __str__(self) -> str:
        return f"MigrationPlan({self.version}_{self.name})"

    def to_dict(self) -> Dict:
        obj = {
            "version": self.version,
            "name": self.name,
            "author": self.author,
            "type": str(self.type),
            "change": self.change.to_dict(),
            "dependencies": [d.to_dict() for d in self.dependencies],
        }
        if self.ignore_after is not None:
            obj["ignore_after"] = self.ignore_after.to_dict()
        return obj

    def get_checksum(self) -> str:
        if self._checksum is not None:
            return self._checksum
        sha1 = helper.SHA1Helper()
        sha1.update_str(self.to_json_str(sort_keys=True))
        forward = self.change.forward
        backward = self.change.backward
        data_dir = os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR)
        match self.type:
            case Type.DATA | Type.REPEATABLE:
                match forward.type:
                    case (
                        DataChangeType.SQL_FILE
                        | DataChangeType.PYTHON
                        | DataChangeType.SHELL
                        | DataChangeType.TYPESCRIPT
                    ):
                        sha1.update_file([os.path.join(data_dir, forward.file)])
                if backward is not None:
                    match backward.type:
                        case (
                            DataChangeType.SQL_FILE
                            | DataChangeType.PYTHON
                            | DataChangeType.SHELL
                            | DataChangeType.TYPESCRIPT
                        ):
                            sha1.update_file([os.path.join(data_dir, backward.file)])
        self._checksum = sha1.hexdigest()
        return self._checksum

    def to_json_str(self, sort_keys: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=4, sort_keys=sort_keys)

    def to_dict_for_log(self):
        obj = self.to_dict()
        obj["checksum"] = self.get_checksum()
        return obj

    def save(self) -> str:
        MigrationSignature(version=self.version, name=self.name).validate(self.type)

        filepath = os.path.join(
            cli_env.MIGRATION_CWD,
            cli_env.MIGRATION_PLAN_DIR,
            f"{self.version}_{self.name}.json",
        )
        logger.info(f"Saved migration plan to {filepath}")
        with open(filepath, "w") as f:
            f.write(self.to_json_str())
        return filepath

    def sig(self) -> MigrationSignature:
        return MigrationSignature(version=self.version, name=self.name)

    def match(self, sig: MigrationSignature) -> bool:
        return self.version == sig.version and self.name == sig.name


@dataclass
class SQLFile:
    name: str
    content: str
    sha1: str


class DiffItemType(StrEnum):
    HEAD = "HEAD"
    VERSION = "VERSION"
    ENVIRONMENT = "ENVIRONMENT"


class SortAlg(StrEnum):
    DEPENDENCY = "DEPENDENCY"  # default
    VERSION = "VERSION"


_default_sort_migration_plans_by = SortAlg.DEPENDENCY
_sort_migration_plans_by = _default_sort_migration_plans_by


class MigrationPlanManager:
    def __init__(self):
        self.plans, self.repeatable_plans = self._read_migration_plans()

    def _read_migration_plans(self) -> Tuple[List[MigrationPlan], List[MigrationPlan]]:
        plans = []
        repeatable_plans = []
        file_dir = os.path.join(cli_env.MIGRATION_CWD, cli_env.MIGRATION_PLAN_DIR)
        for root, _, files in os.walk(file_dir):
            for file in files:
                if not file.endswith(".json"):
                    continue
                with open(os.path.join(root, file)) as f:
                    data = json.load(f)
                    plan = dacite.from_dict(data_class=MigrationPlan, data=data)
                    if plan.type == Type.REPEATABLE:
                        repeatable_plans.append(plan)
                    else:
                        plans.append(plan)
        sorted_plans = MigrationPlanManager._sort_plans(plans)
        MigrationPlanManager._check_dependency_of_repeatable_plans(
            sorted_plans, repeatable_plans
        )
        return sorted_plans, repeatable_plans

    @staticmethod
    def _check_dependency_of_repeatable_plans(
        versioned_plans: List[MigrationPlan],
        repeatable_plans: List[MigrationPlan],
    ) -> None:
        if not repeatable_plans:
            return
        plan_map: Dict[MigrationSignature, MigrationPlan] = {}
        for p in versioned_plans:
            plan_map[p.sig()] = p

        for p in repeatable_plans:
            if len(p.dependencies) == 0:
                continue
            dep = p.dependencies[0]
            if dep not in plan_map:
                raise err.IntegrityError(f"Cannot find dependency {dep} for {p}")

    @staticmethod
    def _sort_plans(plans: List[MigrationPlan]) -> List[MigrationPlan]:
        if _sort_migration_plans_by == SortAlg.VERSION:
            return sorted(plans, key=lambda p: int(p.version))
        elif _sort_migration_plans_by != SortAlg.DEPENDENCY:
            raise Exception(f"Invalid sort algorithm {_sort_migration_plans_by}")

        # Build a dependency graph and sort the plans by topological order
        plan_map: Dict[MigrationSignature, MigrationPlan] = {}
        for p in plans:
            if p.sig() in plan_map:
                raise err.IntegrityError(f"Found duplicate migration plan {p}")
            plan_map[p.sig()] = p
        if InitialMigrationSignature not in plan_map:
            raise err.IntegrityError("Cannot find initial migration plan")

        G = nx.DiGraph()
        G.add_nodes_from([p.sig() for p in plans])

        for p in plans:
            if len(p.dependencies) == 0:
                if p.match(InitialMigrationSignature):
                    continue
                raise err.IntegrityError(f"{p} has no dependency")
            # For now only support one dependency,
            # the other dependencies will be ignored
            dep = p.dependencies[0]
            if dep not in plan_map:
                raise err.IntegrityError(f"Cannot find dependency {dep} for {p}")
            G.add_edge(dep, p.sig())

        # Check for cycles in the graph
        try:
            cycle = nx.algorithms.cycles.find_cycle(G, orientation="original")
            raise err.IntegrityError(f"Dependency cycle detected: {cycle}")
        except nx.exception.NetworkXNoCycle:
            pass

        sorted_plans = []
        # Iterate over all nodes in the graph starting from InitialMigrationSignature
        node: MigrationSignature
        for node in nx.algorithms.traversal.depth_first_search.dfs_preorder_nodes(
            G, InitialMigrationSignature
        ):
            out_degree = G.out_degree(node)
            if out_degree == 0 and len(sorted_plans) != len(plans) - 1:
                # skip the last node
                raise err.IntegrityError(f"Cannot find next migration plan for {node}")
            if out_degree > 1:
                raise err.IntegrityError(
                    f"Found multiple next migration plans for {node}"
                )
            sorted_plans.append(plan_map[node])

        if len(sorted_plans) != len(plans):
            raise Exception(
                f"Found {len(sorted_plans)} sorted_plans but expected {len(plans)}"
            )

        return sorted_plans

    def count(self) -> int:
        return len(self.plans)

    def get_plans(self) -> List[MigrationPlan]:
        return self.plans

    def get_repeatable_plans(self) -> List[MigrationPlan]:
        return self.repeatable_plans

    def get_repeatable_plan_inverse_dependencies(
        self,
    ) -> Dict[MigrationSignature, List[MigrationSignature]]:
        inverse_dependencies = {}
        for plan in self.repeatable_plans:
            for dependency in plan.dependencies:
                if dependency not in inverse_dependencies:
                    inverse_dependencies[dependency] = []
                inverse_dependencies[dependency].append(plan.sig())
        return inverse_dependencies

    def must_get_repeatable_plan_by_signature(
        self, sig: MigrationSignature
    ) -> MigrationPlan:
        for plan in self.repeatable_plans:
            if plan.match(sig):
                return plan
        raise Exception(f"Cannot find repeatable plan for {sig}")

    def get_repeatable_plan(self, name: str) -> MigrationPlan:
        for plan in self.repeatable_plans:
            if plan.name == name:
                return plan
        raise Exception(f"Cannot find repeatable plan with name {name}")

    def get_plans_by_type(self, type: Type) -> List[MigrationPlan]:
        return [p for p in self.plans if p.type == type]

    def get_plan_by_index(self, index: int) -> MigrationPlan:
        return self.plans[index]

    def get_latest_plan(self, type: Optional[Type] = None) -> MigrationPlan:
        if type is None:
            return self.plans[-1]
        for plan in reversed(self.plans):
            if plan.type == type:
                return plan
        raise Exception(f"Cannot find plan with type {type}")

    def get_plan_by_signature(
        self, signature: MigrationSignature
    ) -> List[Optional[Tuple[MigrationPlan, int]]]:
        result = []
        for i, plan in enumerate(self.plans):
            if plan.version == signature.version:
                if signature.name is None or plan.name == signature.name:
                    result.append((plan, i))
        return result

    def must_get_plan_by_signature(
        self, signature: MigrationSignature
    ) -> Tuple[MigrationPlan, int]:
        plans = self.get_plan_by_signature(signature)
        if len(plans) == 0:
            raise Exception(f"Cannot find plan for signature {signature}")
        if len(plans) > 1:
            raise Exception(f"Found multiple plans for signature {signature}")
        return plans[0]

    def must_get_plan_between(
        self,
        left: Optional[MigrationSignature | int | None],
        right: Optional[MigrationSignature | int | None],
    ) -> List[MigrationPlan]:
        if left is None:
            left_idx = 0
        elif isinstance(left, int):
            left_idx = left
        else:
            _, left_idx = self.must_get_plan_by_signature(left)

        if right is None:
            right_idx = len(self.plans) - 1
        elif isinstance(right, int):
            right_idx = right
        else:
            _, right_idx = self.must_get_plan_by_signature(right)

        return self.plans[left_idx : right_idx + 1]

    def get_version_dep_graph(self) -> nx.DiGraph:
        G = nx.DiGraph()
        G.add_nodes_from([i for i in range(len(self.plans))])
        for idx in range(1, len(self.plans)):
            G.add_edge(idx - 1, idx)
            plan = self.plans[idx]
            if plan.change.backward is not None:
                G.add_edge(idx, idx - 1)
        return G
