"""Block Blast solver - entry point.

Usage:
  python main.py solve       # read the board and suggest the best moves
  python main.py read        # read the current board and save a debug image
  python main.py calibrate   # re-measure corners by clicking (rarely needed)

The game window can be behind other windows; it just has to be open
(not minimized).
"""

import sys
import time

from calibrate import calibrate, load_config
from capture import WindowNotFound, grab_window
from overlay import save_suggestion_image
from solver import solve
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
    path = save_suggestion_image(img, config, pieces, moves)
    print(f"\nGorsel oneri kaydedildi: {path}")
    print("(1=kirmizi, 2=turuncu, 3=mavi cerceveler; sayi = hamle sirasi)")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "calibrate":
        calibrate()
    elif command == "read":
        cmd_read()
    elif command == "solve":
        cmd_solve()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
