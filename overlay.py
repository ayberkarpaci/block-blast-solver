"""Draw the suggested moves onto the captured game image."""

import os

import cv2
import numpy as np

from solver import Move
from vision import DEBUG_DIR, scale_point

MOVE_COLORS = [(0, 0, 255), (0, 140, 255), (255, 60, 0)]  # BGR: red, orange, blue


def draw_suggestion(
    img: np.ndarray,
    config: dict,
    pieces: list[np.ndarray | None],
    moves: list[Move],
) -> np.ndarray:
    """Return a copy of the capture with the moves drawn on it."""
    canvas = img.copy()
    n = config["grid_size"]
    x0, y0 = scale_point(config["board_tl"], config, img)
    x1, y1 = scale_point(config["board_br"], config, img)
    cell_w = (x1 - x0) / n
    cell_h = (y1 - y0) / n

    for step, (index, row, col) in enumerate(moves):
        color = MOVE_COLORS[step % len(MOVE_COLORS)]
        shape = pieces[index]
        for r in range(shape.shape[0]):
            for c in range(shape.shape[1]):
                if not shape[r, c]:
                    continue
                px0 = round(x0 + (col + c) * cell_w) + 3
                py0 = round(y0 + (row + r) * cell_h) + 3
                px1 = round(x0 + (col + c + 1) * cell_w) - 3
                py1 = round(y0 + (row + r + 1) * cell_h) - 3
                cv2.rectangle(canvas, (px0, py0), (px1, py1), color, 3)
        # Step number at the piece's first filled cell
        first = np.argwhere(shape)[0]
        tx = round(x0 + (col + first[1] + 0.5) * cell_w) - 10
        ty = round(y0 + (row + first[0] + 0.5) * cell_h) + 10
        cv2.putText(canvas, str(step + 1), (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 3)
    return canvas


def save_suggestion_image(
    img: np.ndarray,
    config: dict,
    pieces: list[np.ndarray | None],
    moves: list[Move],
) -> str:
    os.makedirs(DEBUG_DIR, exist_ok=True)
    canvas = draw_suggestion(img, config, pieces, moves)
    path = os.path.join(DEBUG_DIR, "suggestion.png")
    cv2.imwrite(path, canvas)
    return path
