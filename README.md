# Block Blast Solver

Reads the Block Blast board from the screen (Google Play Games / emulator
window) and will suggest the best moves.

## Setup

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Usage

1. Open the game window and keep it in a fixed position/size.
2. Calibrate once (click the 4 corners on the screenshot that pops up):

   ```
   .venv\Scripts\python main.py calibrate
   ```

3. Read the board:

   ```
   .venv\Scripts\python main.py read
   ```

   Prints the 8x8 matrix and saves `debug/board_read.png` so you can
   verify every cell was read correctly (green square = filled,
   red cross = empty).

If the game window moves or is resized, run `calibrate` again.

## Roadmap

- [x] Step 1: screen capture + corner calibration
- [x] Step 2: 8x8 board reading (filled/empty matrix) + debug image
- [ ] Step 3: read the 3 piece slots and match known piece shapes
- [ ] Step 4: solver (all orders/positions + heuristics)
- [ ] Step 5: overlay/visual suggestion of the best move
