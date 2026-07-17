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
