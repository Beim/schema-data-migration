import random
from typing import List, Tuple

import networkx as nx

from . import consts
from . import migration_plan as mp


class PlanGenerator:
    def __init__(self, graph: nx.DiGraph):
        # read migration plans
        self.graph = graph

    def gen_simple_forward(self) -> List[int]:
        max_node = max(self.graph.nodes)
        return [0, max_node]

    def gen_step_by_step_forward(self) -> List[int]:
        max_node = max(self.graph.nodes)
        result = []
        for i in range(0, max_node + 1):
            result.append(i)
        return result

    def gen_step_by_step_forward_and_backward(self) -> List[int]:
        max_node = max(self.graph.nodes)

        result = []
        max_visited = 0
        while max_visited <= max_node:
            curr = max_visited
            result.append(curr)
            max_visited += 1

            while self.graph.has_edge(curr, curr - 1):
                curr -= 1
                result.append(curr)
        return result

    def gen_monkey(
        self,
        walk_len: int = None,
        start_node: int = 0,
        important_nodes: List[int] = [],
        non_important_nodes: List[int] = [],
    ) -> List[int]:
        G = self.graph.copy()

        if walk_len is None:
            walk_len = (len(G.nodes) - start_node) * 10

        # prevent rollback from the start node
        for n in list(G.succ[start_node]):
            if n < start_node:
                G.remove_edge(start_node, n)

        for i, j in G.edges:
            G[i][j]["weight"] = 4
            if j in important_nodes:
                G[i][j]["weight"] *= 2
            if j in non_important_nodes:
                G[i][j]["weight"] //= 2
            if i < j and not G.has_edge(j, i):
                G[i][j]["weight"] -= 1

        result: List[int] = []

        curr = start_node
        for _ in range(walk_len):
            result.append(curr)
            succ = list(G.succ[curr])
            if len(succ) == 0:
                break
            weight_succ = []
            for s in succ:
                weight = G[curr][s]["weight"]
                weight_succ.extend([s] * weight)
            next_curr = random.choice(weight_succ)
            if G[curr][next_curr]["weight"] > 1:
                G[curr][next_curr]["weight"] -= 1
            curr = next_curr

        return result


class AutoTestPlan:
    def __init__(self):
        self.mpm = mp.MigrationPlanManager()
        self.tpg = PlanGenerator(self.mpm.get_version_dep_graph())

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
