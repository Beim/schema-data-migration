import hashlib
import logging
import os
import random
from typing import List

import networkx as nx

from .env import cli_env

logger = logging.getLogger(__name__)


class SHA1Helper:
    def __init__(self):
        self.sha1 = hashlib.sha1()

    def update_str(self, str_list: List[str]):
        for s in str_list:
            self.sha1.update(s.encode())

    def update_file(self, file_list: List[str]):
        for file in file_list:
            with open(file, "r") as f:
                data = f.read()
            self.sha1.update(data.encode())

    def hexdigest(self) -> str:
        return self.sha1.hexdigest()


def sha1_encode(str_list: List[str]):
    # create a SHA1 hash object
    sha1 = hashlib.sha1()
    # update the hash object with the string
    for s in str_list:
        sha1.update(s.encode())
    # get the hexadecimal representation of the hash
    hex_digest = sha1.hexdigest()
    return hex_digest


def sha1_to_path(sha1: str) -> str:
    return os.path.join(
        cli_env.MIGRATION_CWD,
        cli_env.SCHEMA_STORE_DIR,
        sha1[:2],
        sha1[2:],
    )


def write_sha1_file(sha1: str, content: str):
    folder = os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, sha1[:2])
    filename = sha1[2:]
    # if file exist, return directly, otherwise write file
    filepath = os.path.join(folder, filename)
    logger.debug("Wrote schema store file to %s", filepath)
    if os.path.exists(filepath):
        return
    with open(filepath, "w") as f:
        f.write(content)


def truncate_str(s: str, max_len: int = 40) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."


class TestPlanGenerator:
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
