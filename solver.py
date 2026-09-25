"""Move search.

The 8x8 board is a 64-bit integer bitboard (bit r*8+c = cell filled),
which makes placement tests, line clears and board features a handful
of integer operations.

The search places the tray pieces in every order and every legal
position, clearing full rows/columns after each placement, and scores
each sequence by the points it earns plus an evaluation of the board it
leaves behind. Two caches keep it fast:

- a transposition table: different orders often reach the same board
  with the same pieces left, and only the best-scoring way there needs
  to be explored further;
- an evaluation cache keyed by the board.

The evaluation asks "how likely is the next random piece to fit, and
how much room is left for the awkward ones?", because in Block Blast
you lose by running out of space, not by missing points.
"""

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from pieces import FAMILIES, HARD_SHAPES

N = 8
FULL = (1 << N * N) - 1
ROW_MASKS = [0xFF << (r * N) for r in range(N)]
COL_MASKS = [sum(1 << (r * N + c) for r in range(N)) for c in range(N)]
ROW0, ROW7 = ROW_MASKS[0], ROW_MASKS[7]
COL0, COL7 = COL_MASKS[0], COL_MASKS[7]
NOT_COL7 = FULL & ~COL7
NOT_ROW7 = FULL & ~ROW7

Move = tuple[int, int, int]  # (piece index, row, col)


@dataclass(frozen=True)
class Weights:
    """Heuristic weights, tuned with benchmark.py on simulated games."""

    line: float = 10.0  # per cleared line
    multi_clear: float = 15.0  # per extra line cleared by the same placement
    combo: float = 30.0  # per step of a live combo streak when clearing
    unfit: float = 120.0  # x chance that a random next piece fits nowhere
    hard_room: float = 3.0  # per awkward piece shape that still has room
    hole: float = 6.0  # per empty cell boxed in on all four sides
    transitions: float = 1.5  # per filled/empty boundary inside the board
    filled: float = 0.5  # per filled cell


DEFAULT_WEIGHTS = Weights()


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


def shape_mask(shape: np.ndarray) -> int:
    """Bitmask of a shape placed at the top-left corner."""
    mask = 0
    for r in range(shape.shape[0]):
        for c in range(shape.shape[1]):
            if shape[r, c]:
                mask |= 1 << (r * N + c)
    return mask


def apply_move(board: np.ndarray, shape: np.ndarray, row: int, col: int) -> np.ndarray:
    """Board after placing the piece and clearing full lines."""
    cleared, _ = clear_lines(board_to_bits(board) | shape_mask(shape) << (row * N + col))
    return bits_to_board(cleared)


@lru_cache(maxsize=None)
def _placements(base: int, rows: int, cols: int) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (base << (r * N + c), r, c)
        for r in range(N - rows + 1)
        for c in range(N - cols + 1)
    )


def piece_placements(shape: np.ndarray) -> tuple[tuple[int, int, int], ...]:
    """All positions of a piece as (mask, row, col) of its top-left."""
    return _placements(shape_mask(shape), shape.shape[0], shape.shape[1])


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


def count_transitions(bits: int) -> int:
    """Filled/empty boundaries between neighbouring cells.

    A ragged board has many; a board whose empty space is a few compact
    areas has few, and compact areas are what large pieces need.
    """
    horizontal = (bits ^ (bits >> 1)) & NOT_COL7
    vertical = (bits ^ (bits >> N)) & NOT_ROW7
    return horizontal.bit_count() + vertical.bit_count()


class Fitter:
    """Answers "where does this shape fit?" for a whole board at once.

    For a shape with cells at offsets k1..kn, the empty-cell bitboard
    shifted right by each offset and ANDed together has a bit set at
    every top-left anchor where all n cells are empty.
    """

    def __init__(self, shape: np.ndarray):
        rows, cols = shape.shape
        self.offsets = [r * N + c for r in range(rows) for c in range(cols) if shape[r, c]]
        self.anchors = 0
        for r in range(N - rows + 1):
            for c in range(N - cols + 1):
                self.anchors |= 1 << (r * N + c)

    def positions(self, empty: int) -> int:
        fits = self.anchors
        for k in self.offsets:
            fits &= empty >> k
            if not fits:
                return 0
        return fits


# Next-piece model: uniform over families, then over orientations.
_FAMILY_FITTERS = [[Fitter(s) for s in shapes] for shapes in FAMILIES.values()]
_HARD_FITTERS = [Fitter(s) for s in HARD_SHAPES]


def unfit_chance(bits: int) -> float:
    """Probability that a random next piece fits nowhere on the board."""
    empty = ~bits & FULL
    missing = 0.0
    for fitters in _FAMILY_FITTERS:
        missing += sum(1 for f in fitters if not f.positions(empty)) / len(fitters)
    return missing / len(_FAMILY_FITTERS)


def hard_room(bits: int) -> float:
    """Room left for the awkward shapes: up to 1 per shape, with a second
    spot worth as much as the first, so one lucky gap is not the whole
    story."""
    empty = ~bits & FULL
    room = 0.0
    for fitter in _HARD_FITTERS:
        room += min(fitter.positions(empty).bit_count(), 2) / 2
    return room


# Anchor columns 0..m, for horizontal runs that must not wrap rows.
_COLS_UPTO = [sum(COL_MASKS[: m + 1]) for m in range(N)]
_IRREGULAR = [_FAMILY_FITTERS[list(FAMILIES).index(name)]
              for name in ("corner3", "corner5", "l4", "t4", "s4")]
_CORNER5 = _FAMILY_FITTERS[list(FAMILIES).index("corner5")]


def space_features(bits: int) -> tuple[float, float]:
    """(unfit_chance, hard_room) computed together, fast.

    Lines, squares and rectangles are answered from shared run maps
    (hK = anchors of K empty cells in a row, vK the same in a column),
    and when an empty 3x3 area and 5-long runs both ways exist, every
    piece is known to fit without checking the irregular shapes.
    """
    e = ~bits & FULL
    h2 = e & (e >> 1) & _COLS_UPTO[6]
    h3 = h2 & (e >> 2) & _COLS_UPTO[5]
    h4 = h3 & (e >> 3) & _COLS_UPTO[4]
    h5 = h4 & (e >> 4) & _COLS_UPTO[3]
    v2 = e & (e >> 8)
    v3 = v2 & (e >> 16)
    v4 = v3 & (e >> 24)
    v5 = v4 & (e >> 32)
    sq2 = h2 & (h2 >> 8)
    rect_wide = h3 & (h3 >> 8)  # 2 rows x 3 columns
    rect_tall = sq2 & (h2 >> 16)  # 3 rows x 2 columns
    sq3 = rect_wide & (h3 >> 16)

    corner5 = [f.positions(e) for f in _CORNER5]
    room = (
        min(sq3.bit_count(), 2) + min(h5.bit_count(), 2) + min(v5.bit_count(), 2)
        + min(rect_wide.bit_count(), 2) + min(rect_tall.bit_count(), 2)
        + sum(min(p.bit_count(), 2) for p in corner5)
    ) / 2

    if sq3 and h5 and v5:
        return 0.0, room  # every shape fits inside the 3x3 area or the runs

    missing = (
        (not e)
        + ((not h2) + (not v2)) / 2
        + ((not h3) + (not v3)) / 2
        + ((not h4) + (not v4)) / 2
        + ((not h5) + (not v5)) / 2
        + (not sq2)
        + (not sq3)
        + ((not rect_wide) + (not rect_tall)) / 2
    )
    for fitters in _IRREGULAR:
        if fitters is _CORNER5:
            missing += sum(1 for p in corner5 if not p) / len(fitters)
        else:
            missing += sum(1 for f in fitters if not f.positions(e)) / len(fitters)
    return missing / len(_FAMILY_FITTERS), room


@lru_cache(maxsize=1 << 18)
def evaluate(bits: int, weights: Weights = DEFAULT_WEIGHTS) -> float:
    """How good a board is to be left with (higher is better).

    Cached across calls: after the first move of a tray, the follow-up
    searches visit mostly boards the first search already scored.
    """
    unfit, room = space_features(bits)
    return (
        -weights.unfit * unfit
        + weights.hard_room * room
        - weights.hole * count_holes(bits)
        - weights.transitions * count_transitions(bits)
        - weights.filled * bits.bit_count()
    )


def placement_points(lines: int, streak: int, weights: Weights) -> float:
    """Search reward for a placement that clears `lines` lines."""
    if not lines:
        return 0.0
    gained = weights.line * lines + weights.multi_clear * (lines - 1)
    # The game multiplies points for clearing on consecutive
    # placements, so chains of clears beat isolated ones.
    return gained + weights.combo * streak


def solve(
    board: np.ndarray,
    pieces: list[np.ndarray | None],
    streak: int = 0,
    banned: frozenset[Move] | set[Move] = frozenset(),
    weights: Weights = DEFAULT_WEIGHTS,
) -> tuple[list[Move], float]:
    """Best sequence of placements for the available pieces.

    Returns (moves, score). Prefers sequences that place more pieces;
    among equals, the highest-scoring one. `streak` is the current
    combo count carried over from previous placements, so the search
    knows a live chain is worth protecting. `banned` moves are never
    chosen as the opening move (used after a drag failed to drop).
    """
    available = [i for i, p in enumerate(pieces) if p is not None and p.any()]
    placements = {i: piece_placements(pieces[i]) for i in available}
    shape_key = {i: pieces[i].tobytes() + bytes(pieces[i].shape) for i in available}

    evaluations: dict[int, float] = {}
    # (board, shapes still to place, streak) -> best score seen there
    reached: dict[tuple, float] = {}
    best_moves: list[Move] = []
    best_key = (-1, -math.inf)  # (pieces placed, score)

    def search(bits: int, remaining: tuple[int, ...], moves: list[Move],
               score: float, streak: int) -> None:
        nonlocal best_moves, best_key
        state = (bits, tuple(sorted(shape_key[i] for i in remaining)), streak)
        if reached.get(state, -math.inf) >= score:
            return
        reached[state] = score

        value = evaluations.get(bits)
        if value is None:
            value = evaluations[bits] = evaluate(bits, weights)
        key = (len(moves), score + value)
        if key > best_key:
            best_key = key
            best_moves = moves.copy()

        tried: set[bytes] = set()
        for index in remaining:
            if shape_key[index] in tried:  # identical pieces: one is enough
                continue
            tried.add(shape_key[index])
            rest = tuple(i for i in remaining if i != index)
            for mask, r, c in placements[index]:
                if bits & mask:
                    continue
                if not moves and (index, r, c) in banned:
                    continue
                placed, lines = clear_lines(bits | mask)
                moves.append((index, r, c))
                search(placed, rest, moves, score + placement_points(lines, streak, weights),
                       streak + 1 if lines else 0)
                moves.pop()

    search(board_to_bits(board), tuple(available), [], 0.0, streak)
    return best_moves, best_key[1]
