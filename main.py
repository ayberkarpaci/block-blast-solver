"""Block Blast solver - entry point.

Usage:
  python main.py watch       # live mode: window updates after every move
  python main.py solve       # one-shot: read the board and suggest moves
  python main.py read        # read the current board and save a debug image
  python main.py calibrate   # re-measure corners by clicking (rarely needed)

The game window can be behind other windows; it just has to be open
(not minimized).
"""

import sys
import time

import cv2

from calibrate import calibrate, load_config
from capture import WindowNotFound, grab_window
from overlay import draw_suggestion, save_suggestion_image
from solver import solve

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
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
