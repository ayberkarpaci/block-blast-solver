"""Auto-play: drag the suggested piece from the tray onto the board.

The grab point is the piece's centroid and the drop point is the
center of its target footprint, so it works whether the game holds the
piece by its center or by the grabbed point. An optional
`drag_drop_offset` [dx, dy] in config compensates if the game lifts
the piece away from the cursor while dragging.

Safety: pyautogui's failsafe is active — slam the mouse into the
top-left screen corner to abort immediately.
"""

import time

import numpy as np
import pyautogui
import win32con
import win32gui

from capture import find_window, grab_window
from solver import Move
from vision import piece_grab_points, scale_point, vivid_mask

pyautogui.PAUSE = 0.02
pyautogui.FAILSAFE = True

DRAG_SECONDS = 0.35


def set_topmost(title_part: str, on: bool) -> None:
    """Keep the game above every other window while auto-playing.

    Clicks go to whichever window is on top at that screen position, so
    the game must not be covered (screen capture alone would be fine
    with a background window, but mouse input is not).
    """
    hwnd = find_window(title_part)
    win32gui.SetWindowPos(
        hwnd,
        win32con.HWND_TOPMOST if on else win32con.HWND_NOTOPMOST,
        0, 0, 0, 0,
        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
    )


def focus_window(title_part: str) -> int:
    hwnd = find_window(title_part)
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.4)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass  # Windows may refuse; the click itself will focus the window
    time.sleep(0.25)
    return hwnd


def execute_move(
    img: np.ndarray,
    config: dict,
    pieces: list[np.ndarray | None],
    move: Move,
) -> None:
    """Drag the piece for `move` to its target position.

    The game holds the floating piece far above the cursor, amplifies
    cursor movement, and snaps the piece to the grid near the board, so
    a fixed cursor formula is unreliable. Instead this runs a small
    closed loop: measure where the piece is actually drawn (new vivid
    pixels vs. the pre-drag capture), nudge the cursor by the remaining
    error, repeat until the piece sits on the target, then release.
    """
    index, row, col = move
    shape = pieces[index]
    hwnd = focus_window(config["window_title"])

    grab = piece_grab_points(img, config)[index]
    if grab is None:
        raise RuntimeError(f"Parca {index + 1} artik tepside gorunmuyor.")

    n = config["grid_size"]
    x0, y0 = scale_point(config["board_tl"], config, img)
    x1, y1 = scale_point(config["board_br"], config, img)
    cell_w = (x1 - x0) / n
    cell_h = (y1 - y0) / n

    # Aim for the piece's center of mass (that is what we can measure
    # on screen), not its bounding-box center.
    cells = np.argwhere(shape)
    centroid_r, centroid_c = cells.mean(axis=0)
    target = (
        x0 + (col + centroid_c + 0.5) * cell_w,
        y0 + (row + centroid_r + 0.5) * cell_h,
    )

    base_mask = vivid_mask(img, config)
    # The floating piece is drawn at board scale; require most of it to
    # be visible before trusting a measurement.
    min_pixels = 0.4 * shape.sum() * cell_w * cell_h

    def piece_position() -> tuple[float, float] | None:
        snap = grab_window(config["window_title"])
        diff = vivid_mask(snap, config) & ~base_mask
        ys, xs = np.nonzero(diff)
        if len(xs) < min_pixels:
            return None
        return (float(xs.mean()), float(ys.mean()))

    cursor = grab

    def move_cursor(cx: float, cy: float, duration: float = 0.25) -> tuple[float, float]:
        cx = min(max(cx, 5), img.shape[1] - 5)
        cy = min(max(cy, 5), img.shape[0] - 5)
        sx, sy = win32gui.ClientToScreen(hwnd, (round(cx), round(cy)))
        pyautogui.moveTo(sx, sy, duration=duration)
        return (cx, cy)

    pyautogui.moveTo(*win32gui.ClientToScreen(hwnd, grab))
    pyautogui.mouseDown()
    time.sleep(0.35)

    try:
        gain = 1.3  # cursor movement is amplified roughly this much
        for _ in range(8):
            pos = piece_position()
            if pos is None:
                # Piece lost (drag cancelled?) - abort, caller will retry
                return
            err_x = target[0] - pos[0]
            err_y = target[1] - pos[1]
            if abs(err_x) < cell_w / 3 and abs(err_y) < cell_h / 3:
                break
            cursor = move_cursor(cursor[0] + err_x / gain, cursor[1] + err_y / gain)
            time.sleep(0.3)
    finally:
        time.sleep(0.15)
        pyautogui.mouseUp()
