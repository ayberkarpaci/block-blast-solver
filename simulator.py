"""Headless Block Blast simulator for benchmarking the solver.

Rules modelled: an 8x8 board, a tray of three random pieces that is
refilled once all three are placed, full rows and columns clear after
every placement, and the game ends when no remaining tray piece fits.

The real game's piece distribution and scoring are not public, so both
are approximations: pieces are drawn uniformly by family, then by
orientation, and a placement scores one point per cell plus
10 points per cleared line, multiplied by the number of lines and by
the live combo streak. Benchmarks compare solvers against each other
on the same seeds, so the absolute numbers matter less than the gaps.
"""

import random
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from pieces import FAMILIES
from solver import Move, clear_lines, piece_placements

Policy = Callable[[np.ndarray, list, int], list[Move]]


def random_piece(rng: random.Random) -> np.ndarray:
    family = rng.choice(list(FAMILIES))
    return rng.choice(FAMILIES[family])


@dataclass
class GameResult:
    placed: int = 0
    lines: int = 0
    score: int = 0
    trays: int = 0
    max_combo: int = 0
    moves_log: list = field(default_factory=list)


def play_game(policy: Policy, seed: int, max_placements: int = 600) -> GameResult:
    """Play one game with `policy` and return its statistics.

    The policy gets (board, tray, streak) and returns a plan; only the
    first move is played before asking again, the way auto-play works.
    """
    rng = random.Random(seed)
    bits = 0
    tray: list[np.ndarray | None] = []
    streak = 0
    result = GameResult()

    while result.placed < max_placements:
        if not any(p is not None for p in tray):
            tray = [random_piece(rng) for _ in range(3)]
            result.trays += 1

        board = np.array(
            [[(bits >> (r * 8 + c)) & 1 for c in range(8)] for r in range(8)], dtype=np.uint8
        )
        plan = policy(board, tray, streak)
        if not plan:
            break
        index, row, col = plan[0]
        shape = tray[index]
        mask = next(m for m, r, c in piece_placements(shape) if (r, c) == (row, col))
        if bits & mask:
            raise ValueError(f"policy returned an illegal move {plan[0]}")

        bits, lines = clear_lines(bits | mask)
        streak = streak + 1 if lines else 0
        result.placed += 1
        result.lines += lines
        result.max_combo = max(result.max_combo, streak)
        result.score += int(shape.sum()) + 10 * lines * lines * max(1, streak)
        tray[index] = None

    return result
