import networkx as nx

from migration.auto_test_plan import PlanGenerator


def get_simple_plans() -> nx.DiGraph:
    inputs = [
        [0, 1],
        [1, 0],
        [1, 2],
        [2, 1],
        [2, 3],
        [3, 4],
        [4, 3],
        [4, 5],
        [5, 4],
    ]
    G = nx.DiGraph()
    G.add_edges_from(inputs)
    return G


def test_generate_forward():
    G = get_simple_plans()
    generator = PlanGenerator(G)

    expected = [0, 5]

    got = generator.gen_simple_forward()
    assert got == expected


def test_generate_step_by_step_forward():
    G = get_simple_plans()
    generator = PlanGenerator(G)

    expected = [0, 1, 2, 3, 4, 5]

    got = generator.gen_step_by_step_forward()
    assert got == expected


def test_generate_step_by_step_forward_and_backward():
    G = get_simple_plans()
    generator = PlanGenerator(G)

    expected = [
        0,
        1,
        0,
        2,
        1,
        0,
        3,
        4,
        3,
        5,
        4,
        3,
    ]

    got = generator.gen_step_by_step_forward_and_backward()
    assert got == expected


def test_generate_random_v2():
    G = get_simple_plans()
    generator = PlanGenerator(G)

    X = generator.gen_monkey(
        walk_len=20, start_node=0, important_nodes=[0, 5], non_important_nodes=[]
    )
    print(X)
    assert len(X) == 20
    assert X[0] == 0

    X = generator.gen_monkey(walk_len=20, start_node=2)
    print(X)
    assert len(X) == 20
    assert X[0] == 2
