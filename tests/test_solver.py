import math
import random
from itertools import permutations

import numpy as np
import pytest

from pieces import ALL_SHAPES, FAMILIES
from simulator import play_game
from solver import (
    FULL,
    Fitter,
    apply_move,
    bits_to_board,
    board_to_bits,
    clear_lines,
    count_holes,
    count_transitions,
    evaluate,
    piece_placements,
    hard_room,
    placement_points,
    space_features,
    solve,
    unfit_chance,
    DEFAULT_WEIGHTS,
)


def random_board(rng: random.Random, density: float) -> np.ndarray:
    return np.array([[rng.random() < density for _ in range(8)] for _ in range(8)], dtype=np.uint8)


def test_bits_round_trip():
    board = random_board(random.Random(1), 0.5)
    assert (bits_to_board(board_to_bits(board)) == board).all()


def test_clear_lines_removes_full_row_and_column():
    board = np.zeros((8, 8), dtype=np.uint8)
    board[2, :] = 1
    board[:, 5] = 1
    board[6, 0] = 1
    bits, lines = clear_lines(board_to_bits(board))
    assert lines == 2
    expected = np.zeros((8, 8), dtype=np.uint8)
    expected[6, 0] = 1
    assert (bits_to_board(bits) == expected).all()


def test_apply_move_places_and_clears():
    board = np.zeros((8, 8), dtype=np.uint8)
    board[7, 1:] = 1
    after = apply_move(board, FAMILIES["dot"][0], 7, 0)
    assert after.sum() == 0


def test_piece_placement_count():
    assert len(piece_placements(FAMILIES["square3"][0])) == 36
    assert len(piece_placements(FAMILIES["dot"][0])) == 64


def test_fitter_matches_brute_force():
    rng = random.Random(7)
    for _ in range(40):
        board = random_board(rng, rng.random())
        bits = board_to_bits(board)
        empty = ~bits & FULL
        for shape in ALL_SHAPES:
            expected = {(r, c) for mask, r, c in piece_placements(shape) if not bits & mask}
            fits = Fitter(shape).positions(empty)
            got = {(p // 8, p % 8) for p in range(64) if fits >> p & 1}
            assert got == expected


def test_fast_space_features_match_reference():
    rng = random.Random(11)
    for _ in range(300):
        bits = board_to_bits(random_board(rng, rng.random()))
        unfit, room = space_features(bits)
        assert unfit == pytest.approx(unfit_chance(bits))
        assert room == pytest.approx(hard_room(bits))


def test_board_features():
    assert unfit_chance(0) == 0.0
    assert unfit_chance(FULL) == 1.0
    assert count_transitions(0) == 0
    board = np.ones((8, 8), dtype=np.uint8)
    board[3, 3] = 0
    assert count_holes(board_to_bits(board)) == 1
    assert count_transitions(board_to_bits(board)) == 4


def brute_force(board: np.ndarray, pieces: list, streak: int) -> tuple[int, float]:
    """Exhaustive search without any caching, as a reference."""
    best = (-1, -math.inf)
    start = board_to_bits(board)
    indices = [i for i, p in enumerate(pieces) if p is not None]

    def go(bits, order, placed, score, streak):
        nonlocal best
        best = max(best, (placed, score + evaluate(bits)))
        if not order:
            return
        for mask, _, _ in piece_placements(pieces[order[0]]):
            if bits & mask:
                continue
            new_bits, lines = clear_lines(bits | mask)
            go(new_bits, order[1:], placed + 1,
               score + placement_points(lines, streak, DEFAULT_WEIGHTS),
               streak + 1 if lines else 0)

    for order in permutations(indices):
        go(start, order, 0, 0.0, streak)
    return best


@pytest.mark.parametrize("seed", range(12))
def test_solver_matches_exhaustive_search(seed):
    rng = random.Random(seed)
    board = random_board(rng, 0.6)
    pieces = [rng.choice(ALL_SHAPES) for _ in range(3)]
    streak = rng.choice([0, 0, 2])
    moves, score = solve(board, pieces, streak)
    placed, best = brute_force(board, pieces, streak)
    assert len(moves) == placed
    assert score == pytest.approx(best)


def test_solver_moves_are_legal_in_order():
    rng = random.Random(3)
    board = random_board(rng, 0.4)
    pieces = [rng.choice(ALL_SHAPES) for _ in range(3)]
    moves, _ = solve(board, pieces)
    used = set()
    for index, row, col in moves:
        assert index not in used
        used.add(index)
        shape = pieces[index]
        region = board[row:row + shape.shape[0], col:col + shape.shape[1]]
        assert region.shape == shape.shape
        assert not (region & shape).any()
        board = apply_move(board, shape, row, col)


def test_solver_completes_an_obvious_line():
    board = np.zeros((8, 8), dtype=np.uint8)
    board[0, :7] = 1
    moves, _ = solve(board, [FAMILIES["dot"][0], None, None])
    assert moves == [(0, 0, 7)]


def test_banned_opening_move_is_skipped():
    board = np.zeros((8, 8), dtype=np.uint8)
    board[0, :7] = 1
    moves, _ = solve(board, [FAMILIES["dot"][0], None, None], banned={(0, 0, 7)})
    assert moves and moves[0] != (0, 0, 7)


def test_no_move_when_nothing_fits():
    board = np.ones((8, 8), dtype=np.uint8)
    board[0, 0] = 0
    assert solve(board, [FAMILIES["square2"][0], None, None]) == ([], -math.inf) or \
        solve(board, [FAMILIES["square2"][0], None, None])[0] == []


def test_simulator_is_deterministic():
    policy = lambda board, tray, streak: solve(board, tray, streak)[0]
    first = play_game(policy, seed=5, max_placements=15)
    second = play_game(policy, seed=5, max_placements=15)
    assert (first.placed, first.lines, first.score) == (second.placed, second.lines, second.score)
