"""Block Blast solver - entry point.

Usage:
  python main.py play [n]    # auto-play: drag pieces itself (n = max pieces)
  python main.py watch       # live mode: window updates after every move
  python main.py solve       # one-shot: read the board and suggest moves
  python main.py read        # read the current board and save a debug image
  python main.py calibrate   # re-measure corners by clicking (rarely needed)

Emergency stop for play: slam the mouse into the top-left screen
corner (pyautogui failsafe) or press Ctrl+C in the terminal.

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

SUGGESTION_WINDOW = "Oneri - kapatmak icin ESC"
MAX_POPUP_HEIGHT = 900


def show_popup(canvas) -> None:
    scale = min(1.0, MAX_POPUP_HEIGHT / canvas.shape[0])
    if scale < 1.0:
        canvas = cv2.resize(canvas, None, fx=scale, fy=scale)
    cv2.imshow(SUGGESTION_WINDOW, canvas)
    cv2.setWindowProperty(SUGGESTION_WINDOW, cv2.WND_PROP_TOPMOST, 1)
from vision import (
    format_board,
    format_pieces,
    read_board,
    read_pieces,
    save_debug_image,
)


def cmd_read() -> None:
    try:
        config = load_config()
    except FileNotFoundError:
        print("config.json yok. Once calistir:  python main.py calibrate")
        return

    try:
        img = grab_window(config["window_title"])
    except WindowNotFound as e:
        print(e)
        return

    board = read_board(img, config)
    pieces = read_pieces(img, config)
    print("Okunan tahta (# = dolu, . = bos):\n")
    print(format_board(board))
    print("\nOkunan parcalar:\n")
    print(format_pieces(pieces))
    debug_path = save_debug_image(img, config, board)
    print(f"\nKontrol resmi kaydedildi: {debug_path}")
    print("Yesil kare = dolu okundu, kirmizi carpi = bos okundu.")


def cmd_solve() -> None:
    try:
        config = load_config()
    except FileNotFoundError:
        print("config.json yok. Once calistir:  python main.py calibrate")
        return

    try:
        img = grab_window(config["window_title"])
    except WindowNotFound as e:
        print(e)
        return

    board = read_board(img, config)
    pieces = read_pieces(img, config)
    print("Okunan tahta:\n")
    print(format_board(board))
    print("\nOkunan parcalar:\n")
    print(format_pieces(pieces))

    started = time.perf_counter()
    moves, score = solve(board, pieces)
    elapsed = time.perf_counter() - started

    if not moves:
        print("\nHicbir parca yerlestirilemiyor gibi gorunuyor!")
        return

    print(f"\nOnerilen hamleler (arama {elapsed:.1f} sn, skor {score:.1f}):\n")
    for step, (index, row, col) in enumerate(moves):
        print(f"  {step + 1}. Parca {index + 1} -> satir {row + 1}, sutun {col + 1}")
    save_suggestion_image(img, config, pieces, moves)
    print("\nOneri penceresi acildi: 1=kirmizi, 2=turuncu, 3=mavi; sayi = sira.")
    print("Kapatmak icin pencere seciliyken bir tusa bas.")
    show_popup(draw_suggestion(img, config, pieces, moves))
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def cmd_watch() -> None:
    """Keep a suggestion window open; re-solve whenever the game changes."""
    try:
        config = load_config()
    except FileNotFoundError:
        print("config.json yok. Once calistir:  python main.py calibrate")
        return

    print("Izleme modu acik. Cikmak icin oneri penceresinde ESC'ye bas.")
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
                    "Yeni durum: "
                    + "; ".join(
                        f"{s + 1}. parca {i + 1} -> satir {r + 1}, sutun {c + 1}"
                        for s, (i, r, c) in enumerate(moves)
                    )
                    + f"  (skor {score:.1f})"
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
        f"  ! Parca hedeften ({dr},{dc}) hucre kaymis. config.json'da "
        f"drag_drop_offset degerini [{round(old[0] - dc * cell_w)}, "
        f"{round(old[1] - dr * cell_h)}] yap."
    )


def cmd_play(limit: int | None) -> None:
    try:
        config = load_config()
    except FileNotFoundError:
        print("config.json yok. Once calistir:  python main.py calibrate")
        return

    if limit is None:
        print("Otomatik oynama: oyun bitene veya durdurulana kadar.")
    else:
        print(f"Otomatik oynama: en fazla {limit} parca yerlestirilecek.")
    print("ACIL DURDURMA: mouse'u ekranin SOL UST kosesine carptir veya Ctrl+C.\n")
    import win32api
    from pyautogui import FailSafeException

    from autoplay import focus_window

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
        print("\nACIL FREN: mouse kosede algilandi, durduruldu.")
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
                    print("Restart tiklamalari ise yaramiyor; duruyorum (reklam/bilinmeyen ekran?).")
                    return
                print("Oyun bitmisti - yeni oyun basladi.")
                idle_rounds = 0
                time.sleep(2.0)
                continue
            if idle_rounds > 8:
                print("Tepside parca gorunmuyor; duruyorum (menu/reklam acik olabilir).")
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
        if not moves and (excluded or banned_targets):
            moves, score = solve(board, pieces, streak)
        if not moves:
            # Board is jammed; the game-over screen should appear shortly.
            failed_drags += 1
            if restart_if_game_over(config):
                restarts_without_progress += 1
                if restarts_without_progress > 3:
                    print("Restart tiklamalari ise yaramiyor; duruyorum (reklam/bilinmeyen ekran?).")
                    return
                print("Oyun bitti - yeni oyun basladi.")
                failed_drags = 0
                time.sleep(2.0)
                continue
            if failed_drags > 6:
                print("Yerlestirilebilecek hamle yok ve oyun-bitti ekrani gorunmedi; duruyorum.")
                return
            time.sleep(1.5)
            continue

        chosen = moves[0]
        index, row, col = chosen
        print(f"{placed + 1}. hamle: parca {index + 1} -> satir {row + 1}, sutun {col + 1}")
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
                print("  ! Surukleme 12 kez ise yaramadi, duruyorum.")
                return
            print("  ! Parca yerlesmemis gorunuyor, baska planla deneyecegim.")
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
            print(f"    patlatma! combo zinciri: {streak}")
        if not (after == expected).all():
            suggest_offset(config, board, expected, after, pieces[index], moves[0])
        placed += 1
    print(f"\nBitti: {placed} parca yerlestirildi.")


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
