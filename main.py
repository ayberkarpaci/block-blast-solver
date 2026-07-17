"""Block Blast solver - entry point.

Usage:
  python main.py read        # read the current board and save a debug image
  python main.py calibrate   # re-measure corners by clicking (rarely needed)

The game window can be behind other windows; it just has to be open
(not minimized).
"""

import sys

from calibrate import calibrate, load_config
from capture import WindowNotFound, grab_window
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


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "calibrate":
        calibrate()
    elif command == "read":
        cmd_read()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
