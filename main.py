"""Block Blast solver - entry point.

Usage:
  python main.py calibrate   # click the board / tray corners once
  python main.py read        # read the current board and save a debug image

Solver and overlay steps come later; get `read` working reliably first.
"""

import sys

from calibrate import calibrate, load_config
from capture import grab_screen
from vision import format_board, read_board, save_debug_image


def cmd_read() -> None:
    try:
        config = load_config()
    except FileNotFoundError:
        print("config.json yok. Once calistir:  python main.py calibrate")
        return

    img = grab_screen()
    board = read_board(img, config)
    print("Okunan tahta (# = dolu, . = bos):\n")
    print(format_board(board))
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
