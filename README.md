# Block Blast Solver

Reads the Block Blast board straight from the game window (Google Play
Games / emulator) and suggests the best moves.

The window is captured directly via the Windows PrintWindow API, so it
can sit behind other windows and can be moved or resized freely — it
just must not be minimized.

## Setup

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Usage

With the game window open:

```
.venv\Scripts\python main.py play      # plays by itself until stopped
.venv\Scripts\python main.py play 5    # place at most 5 pieces
```

Auto-play makes the game window topmost (clicks go to whichever
window is on top), grabs a piece, and steers it onto the target cells
with a measure-and-nudge loop before releasing. Emergency stop: slam
the mouse into the top-left screen corner, or Ctrl+C in the terminal.

For suggestions only:

```
.venv\Scripts\python main.py watch     # live suggestion window
.venv\Scripts\python main.py solve     # one-shot suggestion
```

Prints the board, the 3 tray pieces, and the suggested placement order,
and saves `debug/suggestion.png` with the moves drawn on the board
(1 = red, 2 = orange, 3 = blue).

Other commands:

- `main.py read` — just read the board/pieces and save
  `debug/board_read.png` for verification (green square = filled,
  red cross = empty).
- `main.py calibrate` — re-measure the board/tray corners by clicking.
  Only needed if a game update changes the UI layout; coordinates
  scale with the window size automatically.

## How it works

- `capture.py` — grabs the game window's client area (PrintWindow).
- `vision.py` — samples each cell center; a cell is "filled" when it
  is both saturated and bright, which holds across the game's changing
  color themes. Tray pieces are read by masking vivid pixels and
  quantizing the bounding box into ~37px tray cells.
- `solver.py` — 64-bit bitboard search over every distinct piece order
  and position, clearing lines after each placement. Heuristics:
  +10 per cleared line, bonus for multi-line clears, -5 per one-cell
  hole, -20 when no empty 3x3 area remains, small penalty per filled
  cell.
- `overlay.py` — draws the chosen placements onto the capture.
- `autoplay.py` — drags pieces with the real mouse. The game lifts
  the floating piece well above the cursor, amplifies cursor movement,
  and snaps to the grid near the board, so the drag is a closed loop:
  measure where the piece is drawn, nudge the cursor by the remaining
  error, release when it sits on the target cells.
