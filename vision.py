"""Board reading.

The 8x8 board is read by sampling a small patch at the center of each
cell. A cell counts as filled when the patch is both saturated (vivid
color) and bright — this holds across the game's changing themes:
empty cells are either near-white (light themes, low saturation) or
dark navy (dark themes, low brightness), while placed blocks are
always vivid and bright.

Config coordinates were measured at `reference_size`; they are scaled
proportionally to the current capture size, so window resizes are fine
as long as the aspect ratio stays the same.
"""

import os

import cv2
import numpy as np

DEBUG_DIR = "debug"

# A slot is considered empty below this many vivid pixels (in units of
# one tray cell's area). Cells inside a piece's bounding box count as
# occupied above this fill fraction.
MIN_SLOT_FILL = 0.5
CELL_OCCUPANCY = 0.35
MAX_PIECE_SPAN = 5


def scale_point(point: list[int], config: dict, img: np.ndarray) -> tuple[int, int]:
    ref_w, ref_h = config["reference_size"]
    return (
        round(point[0] * img.shape[1] / ref_w),
        round(point[1] * img.shape[0] / ref_h),
    )


def cell_centers(config: dict, img: np.ndarray) -> list[list[tuple[int, int]]]:
    """Pixel center of every cell, as centers[row][col] = (x, y)."""
    n = config["grid_size"]
    x0, y0 = scale_point(config["board_tl"], config, img)
    x1, y1 = scale_point(config["board_br"], config, img)
    cell_w = (x1 - x0) / n
    cell_h = (y1 - y0) / n
    return [
        [
            (round(x0 + (col + 0.5) * cell_w), round(y0 + (row + 0.5) * cell_h))
            for col in range(n)
        ]
        for row in range(n)
    ]


def is_filled(hsv: np.ndarray, cx: int, cy: int, config: dict) -> bool:
    patch = hsv[cy - 3 : cy + 4, cx - 3 : cx + 4]
    saturation = patch[:, :, 1].mean()
    value = patch[:, :, 2].mean()
    return (
        saturation >= config["fill_saturation_threshold"]
        and value >= config["fill_value_threshold"]
    )


def read_board(img: np.ndarray, config: dict) -> np.ndarray:
    """Return an 8x8 uint8 matrix: 1 = filled, 0 = empty."""
    n = config["grid_size"]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    board = np.zeros((n, n), dtype=np.uint8)
    for row, row_centers in enumerate(cell_centers(config, img)):
        for col, (cx, cy) in enumerate(row_centers):
            board[row, col] = 1 if is_filled(hsv, cx, cy, config) else 0
    return board


def vivid_mask(img: np.ndarray, config: dict) -> np.ndarray:
    """Boolean mask of pixels that look like placed/piece blocks."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return (hsv[:, :, 1] >= config["fill_saturation_threshold"]) & (
        hsv[:, :, 2] >= config["fill_value_threshold"]
    )


def tray_background_color(img: np.ndarray, config: dict) -> np.ndarray:
    """Mean color of the strip just above the tray (always background)."""
    x0, y0 = scale_point(config["tray_tl"], config, img)
    x1, _ = scale_point(config["tray_br"], config, img)
    strip = img[max(0, y0 - 25) : max(1, y0 - 8), x0 + 50 : x1 - 50]
    return strip.reshape(-1, 3).mean(axis=0)


def tray_piece_mask(img: np.ndarray, config: dict) -> np.ndarray:
    """Piece pixels = far from the tray background color.

    Vividness is not usable here: some themes (e.g. the orange wood
    event mode) have a background more vivid than the pieces.
    """
    bg = tray_background_color(img, config)
    return np.abs(img.astype(np.int32) - bg.astype(np.int32)).sum(axis=2) > 70


def read_pieces(img: np.ndarray, config: dict) -> list[np.ndarray | None]:
    """Read the 3 tray slots into shape matrices (None = empty slot).

    Each piece is returned as a small 0/1 matrix, e.g. an L piece:
        [[1, 0],
         [1, 0],
         [1, 1]]
    """
    mask = tray_piece_mask(img, config)
    x0, y0 = scale_point(config["tray_tl"], config, img)
    x1, y1 = scale_point(config["tray_br"], config, img)
    cell = config["tray_cell_size"] * img.shape[1] / config["reference_size"][0]
    slot_w = (x1 - x0) / 3

    pieces: list[np.ndarray | None] = []
    for slot in range(3):
        sx0 = round(x0 + slot * slot_w)
        sx1 = round(x0 + (slot + 1) * slot_w)
        sub = mask[y0:y1, sx0:sx1]
        ys, xs = np.nonzero(sub)
        if len(xs) < MIN_SLOT_FILL * cell * cell:
            pieces.append(None)
            continue

        bx0, bx1 = xs.min(), xs.max() + 1
        by0, by1 = ys.min(), ys.max() + 1
        cols = min(MAX_PIECE_SPAN, max(1, round((bx1 - bx0) / cell)))
        rows = min(MAX_PIECE_SPAN, max(1, round((by1 - by0) / cell)))
        shape = np.zeros((rows, cols), dtype=np.uint8)
        for r in range(rows):
            for c in range(cols):
                cy0 = by0 + round(r * (by1 - by0) / rows)
                cy1 = by0 + round((r + 1) * (by1 - by0) / rows)
                cx0 = bx0 + round(c * (bx1 - bx0) / cols)
                cx1 = bx0 + round((c + 1) * (bx1 - bx0) / cols)
                fill = sub[cy0:cy1, cx0:cx1].mean()
                shape[r, c] = 1 if fill >= CELL_OCCUPANCY else 0
        # Mid-animation reads can produce a phantom all-empty shape;
        # treat that as an empty slot rather than a piece.
        pieces.append(shape if shape.any() else None)
    return pieces


def piece_grab_points(img: np.ndarray, config: dict) -> list[tuple[int, int] | None]:
    """Centroid of each tray piece in capture/client coordinates.

    This is where the mouse should grab the piece when auto-playing.
    """
    mask = tray_piece_mask(img, config)
    x0, y0 = scale_point(config["tray_tl"], config, img)
    x1, y1 = scale_point(config["tray_br"], config, img)
    slot_w = (x1 - x0) / 3

    points: list[tuple[int, int] | None] = []
    for slot in range(3):
        sx0 = round(x0 + slot * slot_w)
        sx1 = round(x0 + (slot + 1) * slot_w)
        sub = mask[y0:y1, sx0:sx1]
        ys, xs = np.nonzero(sub)
        if len(xs) == 0:
            points.append(None)
        else:
            points.append((sx0 + round(xs.mean()), y0 + round(ys.mean())))
    return points


def save_debug_image(img: np.ndarray, config: dict, board: np.ndarray) -> str:
    """Save the capture with the detected state drawn on top."""
    os.makedirs(DEBUG_DIR, exist_ok=True)
    canvas = img.copy()
    for row, row_centers in enumerate(cell_centers(config, img)):
        for col, (cx, cy) in enumerate(row_centers):
            filled = board[row, col] == 1
            color = (0, 200, 0) if filled else (0, 0, 255)
            marker = cv2.MARKER_SQUARE if filled else cv2.MARKER_TILTED_CROSS
            cv2.drawMarker(canvas, (cx, cy), color, marker, 14, 2)

    for name in ("board", "tray"):
        tl = scale_point(config[f"{name}_tl"], config, img)
        br = scale_point(config[f"{name}_br"], config, img)
        cv2.rectangle(canvas, tl, br, (255, 0, 255), 1)

    path = os.path.join(DEBUG_DIR, "board_read.png")
    cv2.imwrite(path, canvas)
    return path


def format_board(board: np.ndarray) -> str:
    """Pretty terminal rendering: # = filled, . = empty."""
    return "\n".join(
        " ".join("#" if cell else "." for cell in row) for row in board
    )


def format_pieces(pieces: list[np.ndarray | None]) -> str:
    """Render the 3 tray pieces side by side."""
    blocks = []
    for i, piece in enumerate(pieces):
        lines = [f"Parca {i + 1}:"]
        if piece is None:
            lines.append("(bos)")
        else:
            lines += [" ".join("#" if c else "." for c in row) for row in piece]
        blocks.append(lines)

    height = max(len(b) for b in blocks)
    width = [max(len(line) for line in b) for b in blocks]
    rows = []
    for r in range(height):
        rows.append(
            "   ".join(
                (b[r] if r < len(b) else "").ljust(width[i])
                for i, b in enumerate(blocks)
            ).rstrip()
        )
    return "\n".join(rows)
