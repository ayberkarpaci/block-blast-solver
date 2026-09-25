"""The Block Blast piece set, used by the simulator and the solver's
board evaluation.

Shapes are listed once per orientation, the way they appear in the
tray (pieces cannot be rotated in the game).
"""

import numpy as np


def _shape(rows: str) -> np.ndarray:
    return np.array([[ch == "#" for ch in row] for row in rows.split("/")], dtype=np.uint8)


def _rotations(shape: np.ndarray, mirror: bool = False) -> list[np.ndarray]:
    """Distinct rotations (and, optionally, mirror images) of a shape."""
    candidates = [np.rot90(shape, k) for k in range(4)]
    if mirror:
        candidates += [np.rot90(np.fliplr(shape), k) for k in range(4)]
    distinct: list[np.ndarray] = []
    for c in candidates:
        c = np.ascontiguousarray(c)
        if not any(c.shape == d.shape and (c == d).all() for d in distinct):
            distinct.append(c)
    return distinct


def _build() -> dict[str, list[np.ndarray]]:
    families = {
        "dot": _rotations(_shape("#")),
        "line2": _rotations(_shape("##")),
        "line3": _rotations(_shape("###")),
        "line4": _rotations(_shape("####")),
        "line5": _rotations(_shape("#####")),
        "square2": _rotations(_shape("##/##")),
        "square3": _rotations(_shape("###/###/###")),
        "rect2x3": _rotations(_shape("###/###")),
        "corner3": _rotations(_shape("##/#.")),
        "corner5": _rotations(_shape("###/#../#..")),
        "l4": _rotations(_shape("#./#./##"), mirror=True),
        "t4": _rotations(_shape("###/.#.")),
        "s4": _rotations(_shape(".##/##."), mirror=True),
    }
    return families


FAMILIES: dict[str, list[np.ndarray]] = _build()
ALL_SHAPES: list[np.ndarray] = [s for shapes in FAMILIES.values() for s in shapes]

# Shapes that are hardest to fit; the solver keeps room for them.
HARD_SHAPES: list[np.ndarray] = (
    FAMILIES["square3"] + FAMILIES["line5"] + FAMILIES["corner5"] + FAMILIES["rect2x3"]
)
