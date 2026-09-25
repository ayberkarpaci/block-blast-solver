"""Move search.

The 8x8 board is a 64-bit integer bitboard (bit r*8+c = cell filled),
which makes placement tests and line clears a handful of integer ops.
The search tries every distinct order of the tray pieces and every
legal position, clearing full rows/columns after each placement, and
scores each complete sequence with the heuristics below.
"""

from itertools import permutations

import numpy as np

N = 8
FULL = (1 << N * N) - 1
ROW_MASKS = [0xFF << (r * N) for r in range(N)]
COL_MASKS = [sum(1 << (r * N + c) for r in range(N)) for c in range(N)]
ROW0, ROW7 = ROW_MASKS[0], ROW_MASKS[7]
COL0, COL7 = COL_MASKS[0], COL_MASKS[7]
NOT_2_RIGHT_COLS = FULL & ~COL_MASKS[6] & ~COL_MASKS[7]

# Heuristic weights
LINE_SCORE = 10
MULTI_CLEAR_BONUS = 15  # per extra line cleared in the same move
COMBO_BONUS = 60  # per consecutive clearing placement (combo streak)
HOLE_PENALTY = 5
NO_OPEN_3X3_PENALTY = 20
FILLED_CELL_PENALTY = 0.5


def board_to_bits(board: np.ndarray) -> int:
    bits = 0
    for r in range(N):
        for c in range(N):
            if board[r, c]:
                bits |= 1 << (r * N + c)
    return bits


def bits_to_board(bits: int) -> np.ndarray:
    board = np.zeros((N, N), dtype=np.uint8)
    for r in range(N):
        for c in range(N):
            if bits & (1 << (r * N + c)):
                board[r, c] = 1
    return board


def apply_move(board: np.ndarray, shape: np.ndarray, row: int, col: int) -> np.ndarray:
    """Board after placing the piece and clearing full lines."""
    mask = 0
    for r in range(shape.shape[0]):
        for c in range(shape.shape[1]):
            if shape[r, c]:
                mask |= 1 << ((row + r) * N + (col + c))
    cleared, _ = clear_lines(board_to_bits(board) | mask)
    return bits_to_board(cleared)


def piece_placements(shape: np.ndarray) -> list[tuple[int, int, int]]:
    """All positions of a piece as (mask, row, col) of its top-left."""
    rows, cols = shape.shape
    base = 0
    for r in range(rows):
        for c in range(cols):
            if shape[r, c]:
                base |= 1 << (r * N + c)
    return [
        (base << (r * N + c), r, c)
        for r in range(N - rows + 1)
        for c in range(N - cols + 1)
    ]


def clear_lines(bits: int) -> tuple[int, int]:
    """Remove full rows/columns; return (new_bits, lines_cleared)."""
    clear = 0
    lines = 0
    for mask in ROW_MASKS:
        if bits & mask == mask:
            clear |= mask
            lines += 1
    for mask in COL_MASKS:
        if bits & mask == mask:
            clear |= mask
            lines += 1
    return bits & ~clear, lines


def count_holes(bits: int) -> int:
    """Empty cells whose 4 neighbours are all filled or board edge."""
    empty = ~bits & FULL
    above = ((bits << N) | ROW0) & FULL
    below = (bits >> N) | ROW7
    left = ((bits << 1) & FULL) | COL0
    right = (bits >> 1) | COL7
    return (empty & above & below & left & right).bit_count()


def has_open_3x3(bits: int) -> bool:
    empty = ~bits & FULL
    horizontal = empty & (empty >> 1) & (empty >> 2) & NOT_2_RIGHT_COLS
    return bool(horizontal & (horizontal >> N) & (horizontal >> 2 * N))


def final_board_score(bits: int) -> float:
    score = -HOLE_PENALTY * count_holes(bits)
    score -= FILLED_CELL_PENALTY * bits.bit_count()
    if not has_open_3x3(bits):
        score -= NO_OPEN_3X3_PENALTY
    return score


Move = tuple[int, int, int]  # (piece index, row, col)


def solve(
    board: np.ndarray,
    pieces: list[np.ndarray | None],
    streak: int = 0,
    banned: frozenset[Move] | set[Move] = frozenset(),
) -> tuple[list[Move], float]:
    """Best sequence of placements for the available pieces.

    Returns (moves, score). Prefers sequences that place more pieces;
    among equals, the highest-scoring one. `streak` is the current
    combo count carried over from previous placements, so the search
    knows a live chain is worth protecting.
    """
    available = [(i, p) for i, p in enumerate(pieces) if p is not None and p.any()]
    placements = {i: piece_placements(p) for i, p in available}
    start = board_to_bits(board)

    best_moves: list[Move] = []
    best_key = (-1, float("-inf"))  # (pieces placed, score)

    def search(
        bits: int,
        remaining: tuple[int, ...],
        moves: list[Move],
        score: float,
        streak: int,
    ) -> None:
        nonlocal best_moves, best_key
        key = (len(moves), score + final_board_score(bits))
        if key > best_key:
            best_key = key
            best_moves = moves.copy()
        if not remaining:
            return
        index, rest = remaining[0], remaining[1:]
        for mask, r, c in placements[index]:
            if bits & mask:
                continue
            # Targets that repeatedly failed to drop are skipped as the
            # opening move so the plan starts somewhere else.
            if not moves and (index, r, c) in banned:
                continue
            placed, lines = clear_lines(bits | mask)
            gained = LINE_SCORE * lines
            if lines > 1:
                gained += MULTI_CLEAR_BONUS * (lines - 1)
            # The game multiplies points for clearing with consecutive
            # placements, so chains of clears beat isolated ones.
            if lines:
                gained += COMBO_BONUS * streak
            moves.append((index, r, c))
            search(placed, rest, moves, score + gained, streak + 1 if lines else 0)
            moves.pop()

    seen_orders = set()
    for order in permutations([i for i, _ in available]):
        signature = tuple(pieces[i].tobytes() for i in order)
        if signature in seen_orders:
            continue
        seen_orders.add(signature)
        search(start, order, [], 0.0, streak)

    return best_moves, best_key[1]
