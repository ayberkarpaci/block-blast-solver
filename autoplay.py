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

import cv2
import numpy as np
import pyautogui
import win32con
import win32gui

from capture import find_window, grab_window
from solver import Move
from vision import piece_grab_points, scale_point

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


# Client position (reference-size coords) of the green play button on
# the game-over screen.
GAME_OVER_BUTTON = [465, 1030]


def restart_if_game_over(config: dict) -> bool:
    """Click the play button if an end-of-round screen is showing.

    Button colors vary by screen (green, orange, ...) and some themes
    have vivid backgrounds, so the check is contrast-based: a button at
    that spot differs strongly from the background to its left and
    right, while during play the whole strip is uniform background.
    """
    img = grab_window(config["window_title"])
    x, y = scale_point(GAME_OVER_BUTTON, config, img)

    def region_color(cx: int) -> np.ndarray:
        patch = img[y - 18 : y + 18, max(0, cx - 40) : cx + 40]
        return patch.reshape(-1, 3).mean(axis=0)

    side_offset = round(300 * img.shape[1] / config["reference_size"][0])
    center = region_color(x)
    left = region_color(x - side_offset)
    right = region_color(min(img.shape[1] - 1, x + side_offset))
    if (
        np.abs(center - left).sum() < 120
        or np.abs(center - right).sum() < 120
    ):
        return False
    hwnd = focus_window(config["window_title"])
    pyautogui.click(*win32gui.ClientToScreen(hwnd, (x, y)))
    return True


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

    tray_top = scale_point(config["tray_tl"], config, img)[1]

    # Template of the floating piece at board scale. Position is found
    # by pattern matching instead of a centroid: when the piece passes
    # over already-filled cells those pixels vanish from the diff mask
    # and a centroid drifts badly, but the pattern still lines up on
    # the visible parts.
    SCALE = 0.25
    tmpl = np.zeros((round(shape.shape[0] * cell_h), round(shape.shape[1] * cell_w)), np.float32)
    for r, c in cells:
        tmpl[
            round(r * cell_h) + 4 : round((r + 1) * cell_h) - 4,
            round(c * cell_w) + 4 : round((c + 1) * cell_w) - 4,
        ] = 1.0
    tmpl_small = cv2.resize(tmpl, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_AREA)
    # Centroid of the template, to convert a match location into the
    # same "piece center of mass" space as `target`.
    tmpl_centroid = ((centroid_c + 0.5) * cell_w, (centroid_r + 0.5) * cell_h)
    min_score = 0.3 * float(tmpl_small.sum())

    SEARCH_MARGIN = 350  # the held piece is always this close to the cursor

    def piece_position(hint: tuple[float, float]) -> tuple[float, float] | None:
        # Frame differencing against the pre-drag capture: the moving
        # piece is whatever changed, regardless of theme colors. The
        # search stays near `hint` (around the cursor) so clear
        # animations and score popups elsewhere cannot hijack the match.
        snap = grab_window(config["window_title"])
        diff = (
            np.abs(snap.astype(np.int32) - img.astype(np.int32)).sum(axis=2) > 120
        ).astype(np.float32)
        # The vacated tray slot also differs from the base capture and
        # has the piece's exact shape; keep the tray out of the search.
        diff[tray_top:, :] = 0.0
        wx0 = max(0, round(hint[0]) - SEARCH_MARGIN)
        wy0 = max(0, round(hint[1]) - SEARCH_MARGIN)
        window = diff[wy0 : round(hint[1]) + SEARCH_MARGIN, wx0 : round(hint[0]) + SEARCH_MARGIN]
        small = cv2.resize(window, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_AREA)
        # Pad so a piece partly outside the window can still match.
        pad_y, pad_x = tmpl_small.shape
        small = cv2.copyMakeBorder(small, pad_y, pad_y, pad_x, pad_x, cv2.BORDER_CONSTANT, value=0.0)
        res = cv2.matchTemplate(small, tmpl_small, cv2.TM_CCORR)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val < min_score:
            return None
        return (
            wx0 + (max_loc[0] - pad_x) / SCALE + tmpl_centroid[0],
            wy0 + (max_loc[1] - pad_y) / SCALE + tmpl_centroid[1],
        )

    cursor = grab

    def move_cursor(cx: float, cy: float, duration: float = 0.12) -> tuple[float, float]:
        cx = min(max(cx, 5), img.shape[1] - 5)
        cy = min(max(cy, 5), img.shape[0] - 5)
        sx, sy = win32gui.ClientToScreen(hwnd, (round(cx), round(cy)))
        pyautogui.moveTo(sx, sy, duration=duration)
        return (cx, cy)

    pyautogui.moveTo(*win32gui.ClientToScreen(hwnd, grab))
    pyautogui.mouseDown()
    time.sleep(0.2)

    try:
        gain = 1.3  # cursor movement is amplified roughly this much
        lift = 190.0  # the game holds the piece roughly this far above the cursor
        # Head start: jump to where the target cursor position should
        # be, so the measure loop only has to fine-tune.
        est_piece = (grab[0], grab[1] - lift)
        cursor = move_cursor(
            cursor[0] + (target[0] - est_piece[0]) / gain,
            cursor[1] + (target[1] - est_piece[1]) / gain,
        )
        time.sleep(0.15)

        # The game's cursor-to-piece mapping is nonlinear (movement is
        # amplified more near the top of the board), so the gain is
        # re-estimated each step from how far the piece actually moved.
        gain_x, gain_y = gain, gain
        prev_pos: tuple[float, float] | None = None
        prev_cursor = cursor
        for step in range(10):
            pos = piece_position((cursor[0], cursor[1] - lift * 0.7))
            if pos is None:
                print("    surukleme: parca ekranda bulunamadi (iptal olmus olabilir)")
                return
            if prev_pos is not None:
                dcx = cursor[0] - prev_cursor[0]
                dcy = cursor[1] - prev_cursor[1]
                if abs(dcx) > 4:
                    gain_x = min(6.0, max(0.8, abs(pos[0] - prev_pos[0]) / abs(dcx)))
                if abs(dcy) > 4:
                    gain_y = min(6.0, max(0.8, abs(pos[1] - prev_pos[1]) / abs(dcy)))
            err_x = target[0] - pos[0]
            err_y = target[1] - pos[1]
            print(
                f"    surukleme[{step}]: parca ({pos[0]:.0f},{pos[1]:.0f}) "
                f"hata ({err_x:+.0f},{err_y:+.0f}) imlec ({cursor[0]:.0f},{cursor[1]:.0f}) "
                f"kazanc ({gain_x:.1f},{gain_y:.1f})"
            )
            if abs(err_x) < cell_w / 3 and abs(err_y) < cell_h / 3:
                break
            prev_pos, prev_cursor = pos, cursor
            cursor = move_cursor(cursor[0] + err_x / gain_x, cursor[1] + err_y / gain_y)
            time.sleep(0.15)
    finally:
        time.sleep(0.1)
        pyautogui.mouseUp()
