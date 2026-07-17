"""Board reading.

The 8x8 board is read by sampling a small patch at the center of each
cell. Empty cells on the Block Blast board are dark navy; filled cells
are bright colored blocks, so the HSV value (brightness) channel
separates them cleanly.
"""

import os

import cv2
import numpy as np

DEBUG_DIR = "debug"


def cell_centers(config: dict) -> list[list[tuple[int, int]]]:
    """Pixel center of every cell, as centers[row][col] = (x, y)."""
    n = config["grid_size"]
    x0, y0 = config["board_tl"]
    x1, y1 = config["board_br"]
    cell_w = (x1 - x0) / n
    cell_h = (y1 - y0) / n
    return [
        [
            (round(x0 + (col + 0.5) * cell_w), round(y0 + (row + 0.5) * cell_h))
            for col in range(n)
        ]
        for row in range(n)
    ]


def read_board(img: np.ndarray, config: dict) -> np.ndarray:
    """Return an 8x8 uint8 matrix: 1 = filled, 0 = empty."""
    n = config["grid_size"]
    threshold = config["fill_value_threshold"]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    board = np.zeros((n, n), dtype=np.uint8)
    for row, row_centers in enumerate(cell_centers(config)):
        for col, (cx, cy) in enumerate(row_centers):
            patch = hsv[cy - 3 : cy + 4, cx - 3 : cx + 4]
            value = patch[:, :, 2].mean()
            board[row, col] = 1 if value >= threshold else 0
    return board


def save_debug_image(img: np.ndarray, config: dict, board: np.ndarray) -> str:
    """Save a screenshot crop with the detected state drawn on top."""
    os.makedirs(DEBUG_DIR, exist_ok=True)
    canvas = img.copy()
    for row, row_centers in enumerate(cell_centers(config)):
        for col, (cx, cy) in enumerate(row_centers):
            filled = board[row, col] == 1
            color = (0, 255, 0) if filled else (0, 0, 255)
            marker = cv2.MARKER_SQUARE if filled else cv2.MARKER_TILTED_CROSS
            cv2.drawMarker(canvas, (cx, cy), color, marker, 14, 2)

    # Crop to board + tray with a small margin so the image stays small.
    xs = [config["board_tl"][0], config["board_br"][0], config["tray_tl"][0], config["tray_br"][0]]
    ys = [config["board_tl"][1], config["board_br"][1], config["tray_tl"][1], config["tray_br"][1]]
    margin = 30
    x0 = max(0, min(xs) - margin)
    y0 = max(0, min(ys) - margin)
    x1 = min(canvas.shape[1], max(xs) + margin)
    y1 = min(canvas.shape[0], max(ys) + margin)

    path = os.path.join(DEBUG_DIR, "board_read.png")
    cv2.imwrite(path, canvas[y0:y1, x0:x1])
    return path


def format_board(board: np.ndarray) -> str:
    """Pretty terminal rendering: # = filled, . = empty."""
    return "\n".join(
        " ".join("#" if cell else "." for cell in row) for row in board
    )
