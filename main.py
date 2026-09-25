"""Block Blast solver - entry point.

Usage:
  python main.py play [n]    # auto-play: drag pieces itself (n = max pieces)
  python main.py watch       # live mode: window updates after every move
  python main.py solve       # one-shot: read the board and suggest moves
  python main.py read        # read the current board and save a debug image
  python main.py calibrate   # re-measure corners by clicking (rarely needed)

Emergency stop for play: press ESC. It works from any window, even in
the middle of a drag. (Ctrl+C in the terminal and slamming the mouse
into the top-left screen corner also stop it, but the corner is not
reliable while the bot is moving the mouse.)

The game window can be behind other windows; it just has to be open
(not minimized).
"""

import os
import sys
import time

import cv2

sys.stdout.reconfigure(line_buffering=True)

from autoplay import execute_move, restart_if_game_over, set_topmost
from calibrate import calibrate, load_config
from capture import WindowNotFound, grab_window
from overlay import draw_suggestion, save_suggestion_image
from solver import apply_move, solve
from vision import (
    format_board,
    format_pieces,
    read_board,
    read_pieces,
    save_debug_image,
)

SUGGESTION_WINDOW = "Suggestion - ESC to close"
MAX_POPUP_HEIGHT = 900


def show_popup(canvas) -> None:
    scale = min(1.0, MAX_POPUP_HEIGHT / canvas.shape[0])
    if scale < 1.0:
        canvas = cv2.resize(canvas, None, fx=scale, fy=scale)
    cv2.imshow(SUGGESTION_WINDOW, canvas)
    cv2.setWindowProperty(SUGGESTION_WINDOW, cv2.WND_PROP_TOPMOST, 1)


def cmd_read() -> None:
    try:
        config = load_config()
    except FileNotFoundError:
        print("config.json not found. Run first:  python main.py calibrate")
        return

    try:
        img = grab_window(config["window_title"])
    except WindowNotFound as e:
        print(e)
        return

    board = read_board(img, config)
    pieces = read_pieces(img, config)
    print("Board read (# = filled, . = empty):\n")
    print(format_board(board))
    print("\nPieces read:\n")
    print(format_pieces(pieces))
    debug_path = save_debug_image(img, config, board)
    print(f"\nDebug image saved: {debug_path}")
    print("Green square = read as filled, red cross = read as empty.")


def cmd_solve() -> None:
    try:
        config = load_config()
    except FileNotFoundError:
        print("config.json not found. Run first:  python main.py calibrate")
        return

    try:
        img = grab_window(config["window_title"])
    except WindowNotFound as e:
        print(e)
        return

    board = read_board(img, config)
    pieces = read_pieces(img, config)
    print("Board read:\n")
    print(format_board(board))
    print("\nPieces read:\n")
    print(format_pieces(pieces))

    started = time.perf_counter()
    moves, score = solve(board, pieces)
    elapsed = time.perf_counter() - started

    if not moves:
        print("\nNo piece seems to fit anywhere!")
        return

    print(f"\nSuggested moves (search {elapsed:.2f} s, score {score:.1f}):\n")
    for step, (index, row, col) in enumerate(moves):
        print(f"  {step + 1}. piece {index + 1} -> row {row + 1}, column {col + 1}")
    save_suggestion_image(img, config, pieces, moves)
    print("\nSuggestion window open: 1 = red, 2 = orange, 3 = blue; the number is the order.")
    print("Press any key with the window focused to close it.")
    show_popup(draw_suggestion(img, config, pieces, moves))
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def cmd_watch() -> None:
    """Keep a suggestion window open; re-solve whenever the game changes."""
    try:
        config = load_config()
    except FileNotFoundError:
        print("config.json not found. Run first:  python main.py calibrate")
        return

    print("Watch mode on. Press ESC in the suggestion window to quit.")
    last_state = None
    while True:
        try:
            img = grab_window(config["window_title"])
        except (WindowNotFound, RuntimeError) as e:
            print(e)
            if cv2.waitKey(2000) == 27:
                break
            continue

        board = read_board(img, config)
        pieces = read_pieces(img, config)
        state = (
            board.tobytes(),
            tuple(p.tobytes() if p is not None else b"" for p in pieces),
        )
        if state != last_state:
            last_state = state
            if any(p is not None for p in pieces):
                moves, score = solve(board, pieces)
                print(
                    "New state: "
                    + "; ".join(
                        f"{s + 1}. piece {i + 1} -> row {r + 1}, column {c + 1}"
                        for s, (i, r, c) in enumerate(moves)
                    )
                    + f"  (score {score:.1f})"
                )
                show_popup(draw_suggestion(img, config, pieces, moves))
            else:
                show_popup(img)

        if cv2.waitKey(700) == 27:  # ESC
            break
    cv2.destroyAllWindows()


def suggest_offset(config, board, expected, actual, shape, move) -> None:
    """If the piece landed at a shifted position, print the pixel offset fix."""
    import numpy as np

    diff = (actual == 1) & (board == 0)
    if diff.sum() != shape.sum():
        return
    rows, cols = np.nonzero(diff)
    dr = int(rows.min()) - move[1]
    dc = int(cols.min()) - move[2]
    if (dr, dc) == (0, 0):
        return
    n = config["grid_size"]
    cell_w = (config["board_br"][0] - config["board_tl"][0]) / n
    cell_h = (config["board_br"][1] - config["board_tl"][1]) / n
    old = config.get("drag_drop_offset", [0, 0])
    print(
        f"  ! The piece landed ({dr},{dc}) cells off target. Set drag_drop_offset "
        f"in config.json to [{round(old[0] - dc * cell_w)}, "
        f"{round(old[1] - dr * cell_h)}]."
    )


def cmd_play(limit: int | None) -> None:
    try:
        config = load_config()
    except FileNotFoundError:
        print("config.json not found. Run first:  python main.py calibrate")
        return

    if limit is None:
        print("Auto-play: until the game ends or you stop it.")
    else:
        print(f"Auto-play: placing at most {limit} pieces.")
    print("EMERGENCY STOP: press ESC (works from any window, even mid-drag).\n")
    import win32api
    import win32con
    from pyautogui import FailSafeException

    from autoplay import focus_window
    from emergency import watch_for_escape

    def emergency_stop() -> None:
        # Let go of a piece that is mid-drag, and give the screen back.
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        set_topmost(config["window_title"], False)
        print("\nEMERGENCY STOP: ESC pressed, stopped.", flush=True)

    watch_for_escape(emergency_stop)

    # If the last run was stopped by slamming the mouse into the
    # top-left corner, the cursor is still parked there and would
    # instantly re-trigger the failsafe.
    if win32api.GetCursorPos() <= (10, 10):
        win32api.SetCursorPos((400, 400))

    focus_window(config["window_title"])  # restores the window if minimized
    set_topmost(config["window_title"], True)
    try:
        play_loop(config, limit)
    except FailSafeException:
        print("\nEMERGENCY STOP: mouse detected in the corner, stopped.")
    finally:
        set_topmost(config["window_title"], False)


def play_loop(config: dict, limit: int | None) -> None:
    placed = 0
    idle_rounds = 0
    failed_drags = 0
    streak = 0  # live combo count, carried into the solver
    last_failed_piece: int | None = None
    banned_targets: set[tuple[int, int, int]] = set()
    restarts_without_progress = 0
    while limit is None or placed < limit:
        try:
            img = grab_window(config["window_title"])
        except WindowNotFound as e:
            print(e)
            return

        # Wait until two consecutive reads agree so we never act on a
        # board captured mid-animation.
        board = read_board(img, config)
        pieces = read_pieces(img, config)
        for _ in range(10):
            time.sleep(0.15)
            img2 = grab_window(config["window_title"])
            board2 = read_board(img2, config)
            pieces2 = read_pieces(img2, config)
            same_pieces = len(pieces) == len(pieces2) and all(
                (a is None and b is None)
                or (a is not None and b is not None and a.shape == b.shape and (a == b).all())
                for a, b in zip(pieces, pieces2)
            )
            if (board == board2).all() and same_pieces:
                break
            img, board, pieces = img2, board2, pieces2

        if all(p is None for p in pieces):
            idle_rounds += 1
            if idle_rounds >= 3 and restart_if_game_over(config):
                restarts_without_progress += 1
                if restarts_without_progress > 3:
                    print("Restart clicks are not working; stopping (an ad or an unknown screen?).")
                    return
                print("The game was over - started a new one.")
                idle_rounds = 0
                time.sleep(2.0)
                continue
            if idle_rounds > 8:
                print("No pieces in the tray; stopping (a menu or an ad may be open).")
                return
            time.sleep(1.0)
            continue
        idle_rounds = 0

        # After a failed drag, try a fresh plan that starts with a
        # different piece. (Never fall back to a later move of the same
        # plan - those assume the earlier moves were already played.)
        solve_input = list(pieces)
        excluded = last_failed_piece is not None and sum(p is not None for p in pieces) > 1
        if excluded:
            solve_input[last_failed_piece] = None
        moves, score = solve(board, solve_input, streak, banned_targets)
        if not moves and excluded:
            # Keep the bans: dropping them here made the bot retry the
            # exact target that just failed, over and over.
            moves, score = solve(board, pieces, streak, banned_targets)
        if not moves and banned_targets:
            moves, score = solve(board, pieces, streak)
        if not moves:
            # Board is jammed; the game-over screen should appear shortly.
            failed_drags += 1
            if restart_if_game_over(config):
                restarts_without_progress += 1
                if restarts_without_progress > 3:
                    print("Restart clicks are not working; stopping (an ad or an unknown screen?).")
                    return
                print("Game over - started a new one.")
                failed_drags = 0
                time.sleep(2.0)
                continue
            if failed_drags > 6:
                print("No move fits and no game-over screen appeared; stopping.")
                return
            time.sleep(1.5)
            continue

        chosen = moves[0]
        index, row, col = chosen
        print(f"Move {placed + 1}: piece {index + 1} -> row {row + 1}, column {col + 1}")
        try:
            execute_move(img, config, pieces, chosen)
        except RuntimeError as e:
            print(f"  ! {e}")
            time.sleep(0.8)
            continue
        time.sleep(0.6)

        # Clear/celebration animations can corrupt a single read right
        # after the drop; wait until two consecutive reads agree before
        # judging whether the piece landed.
        after_img = grab_window(config["window_title"])
        after = read_board(after_img, config)
        for _ in range(6):
            time.sleep(0.25)
            img3 = grab_window(config["window_title"])
            board3 = read_board(img3, config)
            if (board3 == after).all():
                break
            after_img, after = img3, board3

        # A placed piece always leaves its tray slot, so a changed slot
        # is placement evidence even when the board read glitches.
        tray_now = read_pieces(after_img, config)
        slot_same = (
            tray_now[index] is not None
            and tray_now[index].shape == pieces[index].shape
            and (tray_now[index] == pieces[index]).all()
        )
        expected = apply_move(board, pieces[index], row, col)
        if (after == board).all() and slot_same:
            failed_drags += 1
            last_failed_piece = index
            banned_targets.add(chosen)
            os.makedirs(os.path.join("debug", "fails"), exist_ok=True)
            stamp = time.strftime("%H%M%S")
            cv2.imwrite(os.path.join("debug", "fails", f"{stamp}_before.png"), img)
            cv2.imwrite(os.path.join("debug", "fails", f"{stamp}_after.png"), after_img)
            from autoplay import dump_last_drag

            dump_last_drag(os.path.join("debug", "fails", stamp))
            if failed_drags >= 12:
                print("  ! 12 drags in a row failed; stopping.")
                return
            print("  ! The piece does not seem to have landed; trying another plan.")
            # An event popup or celebration can eat drops for a while;
            # back off so the transient state passes instead of burning
            # every retry inside it.
            time.sleep(0.8 if failed_drags < 3 else 8.0)
            continue
        failed_drags = 0
        last_failed_piece = None
        banned_targets.clear()
        restarts_without_progress = 0
        # Did this placement clear lines? (cells after < cells before + piece)
        cleared = int(board.sum()) + int(pieces[index].sum()) > int(after.sum())
        streak = streak + 1 if cleared else 0
        if cleared:
            print(f"    cleared! combo streak: {streak}")
        if not (after == expected).all():
            suggest_offset(config, board, expected, after, pieces[index], moves[0])
        placed += 1
    print(f"\nDone: placed {placed} pieces.")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "calibrate":
        calibrate()
    elif command == "read":
        cmd_read()
    elif command == "solve":
        cmd_solve()
    elif command == "watch":
        cmd_watch()
    elif command == "play":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        cmd_play(limit)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
