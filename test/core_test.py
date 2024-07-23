import numpy as np
from splitcycle import core

pytest_plugins = ("benchmark",)


def gen_ballots(orders, rcounts):
    ballots = []
    for i in range(len(rcounts)):
        for j in range(rcounts[i]):
            ballots.append(orders[i])
    return np.array(ballots)


ballots = gen_ballots(
    [
        [4, 3, 2, 5, 1],
        [3, 2, 1, 4, 5],
        [3, 2, 5, 4, 1],
        [2, 4, 3, 1, 5],
        [4, 3, 1, 2, 5],
        [3, 4, 5, 1, 2],
    ],
    [4, 3, 7, 7, 2, 1],
)


def test_elect_DFS(benchmark):
    result = benchmark(core.elect, ballots, [1, 2, 3, 4, 5])
    assert result == [4]


def test_BFS(benchmark):
    result = benchmark(core.elect, ballots, [1, 2, 3, 4, 5], dfs=False)
    assert result == [4]
