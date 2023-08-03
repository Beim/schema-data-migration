from typing import List, Tuple

from . import consts, helper
from . import migration_plan as mp

"""
Sample test plan
[
    "0000_init",
    "0001_add_column",
    "0002_seed_data",
    "0003_add_column",
]
"""


class AutoTestPlan:
    def __init__(self):
        self.mpm = mp.MigrationPlanManager()
        self.tpg = helper.TestPlanGenerator(self.mpm.get_version_dep_graph())

    def read_test_plan(
        self, test_plan_content: List[str]
    ) -> List[Tuple[mp.MigrationPlan, int]]:
        plans = []
        for line in test_plan_content:
            sig = mp.MigrationSignature.from_str(line)
            plan = self.mpm.must_get_plan_by_signature(sig)
            plans.append(plan)
        return plans

    def _parse_idx_plan_to_str(self, idx_plan: List[int]) -> List[str]:
        plan = []
        for idx in idx_plan:
            plan.append(str(self.mpm.get_plans()[idx].sig()))
        return plan

    def _parse_str_plan_to_idx(self, str_plan: List[str]) -> List[int]:
        res = []
        for s in str_plan:
            sig = mp.MigrationSignature.from_str(s)
            _, idx = self.mpm.must_get_plan_by_signature(sig)
            res.append(idx)
        return res

    def gen(
        self,
        test_type: str,
        walk_len: int = None,
        start: str = "",
        important: str = "",
        non_important: str = "",
    ) -> List[str]:
        match test_type:
            case consts.TEST_TYPE_SIMPLE_FORWARD:
                test_plan = self.gen_simple_forward()
            case consts.TEST_TYPE_STEP_FORWARD:
                test_plan = self.gen_step_by_step_forward()
            case consts.TEST_TYPE_STEP_BACKWARD:
                test_plan = self.gen_step_by_step_forward_and_backward()
            case consts.TEST_TYPE_MONKEY:
                if not start:
                    start_node = 0
                else:
                    start_node = self._parse_str_plan_to_idx([start])[0]
                if not important:
                    important_nodes = []
                else:
                    important_nodes = self._parse_str_plan_to_idx(important.split(","))
                if not non_important:
                    non_important_nodes = []
                else:
                    non_important_nodes = self._parse_str_plan_to_idx(
                        non_important.split(",")
                    )
                test_plan = self.gen_monkey(
                    walk_len=walk_len,
                    start_node=start_node,
                    important_nodes=important_nodes,
                    non_important_nodes=non_important_nodes,
                )
            case _:
                raise Exception(f"Unknown test type: {test_type}")
        return test_plan

    def gen_simple_forward(self) -> List[str]:
        idx_plan = self.tpg.gen_simple_forward()
        return self._parse_idx_plan_to_str(idx_plan)

    def gen_step_by_step_forward(self) -> List[str]:
        idx_plan = self.tpg.gen_step_by_step_forward()
        return self._parse_idx_plan_to_str(idx_plan)

    def gen_step_by_step_forward_and_backward(self) -> List[str]:
        idx_plan = self.tpg.gen_step_by_step_forward_and_backward()
        return self._parse_idx_plan_to_str(idx_plan)

    def gen_monkey(
        self,
        walk_len: int = None,
        start_node: int = 0,
        important_nodes: List[int] = [],
        non_important_nodes: List[int] = [],
    ) -> List[str]:
        idx_plan = self.tpg.gen_monkey(
            walk_len=walk_len,
            start_node=start_node,
            important_nodes=important_nodes,
            non_important_nodes=non_important_nodes,
        )
        return self._parse_idx_plan_to_str(idx_plan)
