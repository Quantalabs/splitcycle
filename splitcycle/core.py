"""Core utilities for SplitCycle package"""

import os
from multiprocessing import Pool
import numpy as np
from .errors import not_enough_candidates
from collections import deque


def is_square(matrix):
    """Check if `matrix` is 2D and square"""
    return (len(matrix.shape) == 2) and (matrix.shape[0] == matrix.shape[1])


def has_reverse_diagonal_symmetry(matrix):
    """
    Check if `matrix` is 2D square with reverse diagonal symmetry
    i.e. `A[i, j] == -A[j, i]` for all `i, j`
    """
    return is_square(matrix) and np.allclose(matrix, -matrix.T)


def has_zero_diagonal(matrix):
    """
    Check if `matrix` is 2D square with zero diagonal entries
    i.e. `A[i, i] == 0` for all `i`
    """
    return is_square(matrix) and np.allclose(matrix.diagonal(), 0)


def is_margin_like(matrix):
    """
    Check if `matrix` can be used as a voting margins matrix satisfying
    reverse diagonal symmetry and with zero diagonal entries
    """
    return has_reverse_diagonal_symmetry(matrix) and has_zero_diagonal(matrix)


def is_splitcycle_winner(work):
    """
    Determine which candidates satisfy the criteria to be considered
    SplitCycle winners

    `work`:
        tuple with:
        (all_candidates, dfs, considered_candidates, margins)

    Returns a pruned list of identified winners
    """

    def has_strong_path(matrix, source, target, k):
        """
        Given a square `matrix`, return `True` if there is a path from
        `source` to `target` in the associated directed graph, where
        each edge has a weight greater than or equal to `k`, and `False`
        otherwise.
        """
        n = matrix.shape[0]  # `A` is square
        if source == target:
            return True

        s_visited = np.zeros(n, dtype=bool)
        t_visited = np.zeros(n, dtype=bool)
        s_visited[source] = True
        t_visited[target] = True

        sq = deque([source])
        tq = deque([target])

        cs = None
        ct = None

        while sq and tq:
            if sq:
                cs = sq.popleft()
                for neighbor, weight in enumerate(matrix[cs]):
                    if weight >= k:
                        if t_visited[neighbor]:
                            return True
                        if not s_visited[neighbor]:
                            s_visited[neighbor] = True
                            sq.append(neighbor)

            if tq:
                ct = tq.popleft()
                for neighbor in range(n):
                    if matrix[neighbor, ct] >= k:
                        if s_visited[neighbor]:
                            return True
                        if not t_visited[neighbor]:
                            t_visited[neighbor] = True
                            tq.append(neighbor)

        return False

    def has_strong_path_dfs(matrix, source, target, k):
        """
        Given a square `matrix`, return `True` if there is a path from
        `source` to `target` in the associated directed graph, where
        each edge has a weight greater than or equal to `k`, and `False`
        otherwise.

        This function is equivalent to `has_strong_path` but uses a
        depth-first search implementation instead of breadth-first
        search when searching for strong paths. It is included for
        comparison and testing purposes.
        """
        n = matrix.shape[0]  # `A` is square
        # keep track of visited nodes (initially all `False`)
        visited = np.zeros(n, dtype=bool)

        def dfs(node):
            """
            Depth-first search implementation:
            Search starting from `node` in `matrix` until a path to
            `target` is found or until all nodes are searched.
            """
            if node == target:
                # path to target exists
                return True

            visited[node] = True  # mark node as visited

            # search all neighbors that have not been visited
            for neighbor, weight in enumerate(matrix[node, :]):
                if weight >= k and not visited[neighbor]:
                    if dfs(neighbor):
                        return True

            return False

        return dfs(source)

    all_candidates = work[0]
    dfs = work[1]
    finder = has_strong_path_dfs if dfs else has_strong_path
    considered_candidates = work[2]
    winners = set(considered_candidates)
    margins = work[3]

    for a in considered_candidates:
        # `a` is not a Condorcet winner
        # if it loses to `b`:
        # >>>   margins[a, b] < 0,
        # in which case `a` is a SplitCycle winner only
        # if it is locked into a Condorcet cycle with `b`:
        # >>>   (margins[a, b] < 0) and \
        # ...       has_strong_path(margins, a, b, 1)
        # and
        # if the path in which `b` defeats `a` is one of the weakest
        # paths in that cycle:
        # >>>   has_strong_path(margins, a, b, -margins[a, b])
        # putting this altogether, we need to remove `a` from the
        # list of Condorcet winners
        # if `a` loses to `b` and there is no Condorcet cycle
        # including `a` and `b` where the path in which `b` defeats
        # `a` is one of the weakest paths in that cycle:
        # >>>   (margins[a, b] < 0) and not \
        # ...       has_strong_path(margins, a, b, -margins[a, b])
        for b in all_candidates:
            if (margins[a, b] < 0) and not finder(
                margins, a, b, -margins[a, b]
            ):
                winners.discard(a)
                break

    return winners


def splitcycle(margins, candidates=None, dfs=True):
    """
    If x has a positive margin over y and there is no path from y back
    to x of strength at least the margin of x over y, then x defeats y.
    The candidates that are undefeated are the Split Cycle winners.

    `margins`:
        a square matrix with margins of victory (positive) or defeat
        (negative) between candidates on its first axis and their
        opponents on the second; should be symmetric over the diagonal
        (which should be zero, as candidates cannot defeat themselves)

    `candidates=None`:
        if `None`, use the candidates in `margins`

    `dfs=True`:
        if `False`, use breadth-first search instead of default
        depth-first search implementation

    Returns a sorted list of all SplitCycle winners
    """
    if not is_margin_like(margins):
        raise TypeError(
            "`margins` must be a square matrix with diagonal symmetry "
            "and zero diagonal entries. `margins` represents a "
            "directed graph as a square matrix, where `margins[i, j]` "
            "represents the signed margin of victory (positive) or "
            "defeat (negative) of candidate `i` against `j`. The "
            "reverse election (candidate `j` against `i`) is "
            "represented by `margins[j, i]` and should be equal to "
            "`-margins[i, j]`. Additionally, the election of candidate "
            "`i` against itself should have zero margin (i.e. "
            "`margins[i, i] == 0`). As all preferences are compared to "
            "each other, this matrix should include weights (margins) "
            "between any two candidates (zero if tied).\n\n"
            "The current `margins` matrix does not satisfy one of "
            "these properties:\n"
            "  - 2D array\n"
            "  - square matrix\n"
            "  - reverse diagonal symmetry\n"
            "  - zero diagonal\n"
        )

    n = margins.shape[0]  # `margins` is square

    # consider all candidates when first called
    candidates = range(n) if candidates is None else candidates

    # prepare multithreading pool
    cores = os.cpu_count()
    candidates_per_core = n // cores
    # distribute workload as equally as possible across available cores
    pool_sizes = [
        (candidates_per_core + 1) if (i < n % cores) else candidates_per_core
        for i in range(cores)
    ]

    # initialize workload by partitioning candidate indices across cores
    work = []
    start = 0
    for size in pool_sizes:
        work.append((candidates, dfs, range(start, start + size), margins))
        start += size

    # start multithreading
    with Pool(cores) as executor:
        result = executor.map(is_splitcycle_winner, work)

    # gather results
    winners = set.union(*result)

    return sorted(winners)


def margins_from_ballots(ballots):
    """
    Turn a set of ballots (as described in `elect`) into a voting
    margins matrix (as described in `splitcycle`)
    """
    # generate initial margins matrix
    n_candidates = ballots.shape[1]
    margins = np.zeros((n_candidates, n_candidates))

    for ballot in ballots:
        comp = np.subtract.outer(ballot, ballot)

        margins += np.where(comp < 0, 1, np.where(comp > 0, -1, 0))

    return margins


def elect(ballots, candidates, dfs=True):
    """
    Determine the SplitCycle winners given a set of `ballots` and
    `candidates`

    `ballots`:
        a list of ballots, where each ballot is a list of candidate
        ranks; lower ranks indicate more preferred candidates (i.e. if
        candidate A has rank a and candidate B has rank b, A is
        preferred to B if a < b, A and B are tied if a = b, and B is
        preferred to A if a > b). All candidates (including unranked
        candidates) should have a rank (unranked candidates should all
        have an equal rank greater than the rank of the least preferred
        ranked candidate)

        Example:
        >>> ballots = np.array([
        ...     # candidates are A, B, C, D
        ...     [1, 2, 3, 4],  # candidates ranked in sequential order
        ...     [3, 1, 1, 2],  # candidates B and C tied for first place
        ...     [1, 1, 1, 2],  # candidates A, B, and C tied, D unranked
        ... ])

    `candidates`:
        a list of candidate names, where the index of each name
        corresponds to the index of the candidate in each ballot

    `dfs=True`:
        if `True`, use depth-first search to determine the SplitCycle
        winners; if `False`, use breadth-first search

    Returns a sorted list of all SplitCycle winners
    """
    # check that all candidates are represented in `ballots`
    if ballots.shape[1] != len(candidates):
        not_enough_candidates()

    # run `splitcycle`
    margins = margins_from_ballots(ballots)
    winner_indices = splitcycle(margins, dfs=dfs)

    # map winner indices to candidate names
    return [candidates[i] for i in winner_indices]
