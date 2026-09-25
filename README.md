# Block Blast Solver

[![tests](https://github.com/ayberkarpaci/block-blast-solver/actions/workflows/tests.yml/badge.svg)](https://github.com/ayberkarpaci/block-blast-solver/actions/workflows/tests.yml)

Reads the Block Blast board straight from the game window (Google Play
Games on Windows), finds the best placements for the three tray pieces,
and can play the game by itself with the real mouse.

- **Vision:** captures the window with the Windows PrintWindow API (it can
  sit behind other windows) and reads the 8x8 board and the tray pieces
  across the game's changing color themes.
- **Solver:** exhaustive bitboard search over every piece order and
  position, scored by an evaluation that estimates how likely the next
  random piece is to fit. On simulated games it survives about 4.5 times longer than the
  previous heuristic.
- **Auto-play:** drags each piece with a closed measure-and-nudge loop,
  recovers from dropped drags and restarts the round on game over.

## Setup

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Usage

With the game window open (it can be behind other windows, just not
minimized):

```
.venv\Scripts\python main.py play      # plays by itself until stopped
.venv\Scripts\python main.py play 5    # place at most 5 pieces
.venv\Scripts\python main.py watch     # live suggestion window
.venv\Scripts\python main.py solve     # one-shot suggestion
.venv\Scripts\python main.py read      # check what the vision reads
.venv\Scripts\python main.py calibrate # re-measure the layout (rarely needed)
```

Auto-play makes the game window topmost (clicks go to whichever window is
on top), grabs a piece and steers it onto the target cells before
releasing. **Emergency stop: press ESC.** It works from any window,
even in the middle of a drag: the bot lets go of the piece, drops the
game window's always-on-top flag and exits at once. Ctrl+C in the
terminal works too. (The top-left-corner mouse failsafe is still on, but
it is not reliable while the bot itself is moving the mouse.)

`solve` and `watch` draw the plan onto the captured board
(1 = red, 2 = orange, 3 = blue) and save `debug/suggestion.png`.

## The solver

The board is a 64-bit integer (bit `r*8+c` = cell filled), so placing a
piece, testing for overlap and clearing lines are a few integer
operations.

**Search.** Every order of the tray pieces and every legal position is
tried, clearing full rows and columns after each placement. Sequences
that place more pieces always win; among those, the score is the points
earned along the way (lines, multi-line clears, a live combo streak) plus
an evaluation of the board left behind. Two caches keep it fast:

- a transposition table: different orders often reach the same board
  with the same pieces left, and only the best-scoring way there is
  explored further;
- an evaluation cache shared between moves: after the first placement
  of a tray, the next searches mostly revisit boards already scored.

The search is exact: a test compares it with a plain exhaustive search on
random positions and requires identical results.

**Evaluation.** You lose Block Blast by running out of room, not by
missing points, so the evaluation looks ahead to the next random pieces:

| Term | Meaning |
|---|---|
| Unfit chance | Probability that a random next piece fits nowhere (computed over the whole piece set) |
| Room for awkward shapes | Whether 3x3 squares, 1x5 bars, 5-cell corners and 2x3 blocks still have one or two spots |
| Holes | Empty cells boxed in on all four sides |
| Transitions | Filled/empty boundaries; a ragged board has many, compact open areas few |
| Filled cells | Fewer is better |

Fit tests use shifted bitboards: for a shape with cells at offsets
k1..kn, `empty >> k1 & ... & empty >> kn` marks every anchor where the
shape fits. Lines, squares and rectangles share run maps (cells with K
empty neighbours in a row or column), and when an empty 3x3 area and
5-long runs both exist the solver knows every piece fits without
checking the rest.

## Benchmark

`simulator.py` plays Block Blast headlessly (8x8 board, trays of three
random pieces, line clears, game over when nothing fits), and
`benchmark.py` runs the solver on seeded games in parallel:

```
.venv\Scripts\python benchmark.py --games 100 --cap 500
```

Results on seeds 0-99, games stopped at 500 pieces:

| Solver | Pieces placed (mean / median) | Lines cleared | Score | Think time |
|---|---|---|---|---|
| Previous heuristic (holes, filled cells, open 3x3) | 76.6 / 73.5 | 35.6 | 887 | 149 ms |
| Current solver | **346.6 / 384** | **177.2** | **4438** | 171 ms |

36 of the 100 games reached the 500-piece cap. Think time was measured
with 16 games running in parallel; a single search on an idle machine
averages about 50 ms per move over a game (up to about 150 ms for a full
tray on an open board).

The biggest gain came from the evaluation: the unfit-chance and
room-for-awkward-shapes terms alone took the mean from 76.6 to 316.6
pieces. Tuning the weights (one coordinate-search round on 64 separate
games, keeping changes that added more than 8 pieces) raised it to 346.6.

The real game's piece distribution is not public; the simulator draws
pieces uniformly by family and is harsher than the game, which tends to
hand out pieces that fit. The weights were tuned on a separate set of
seeds (1000+) from the ones reported above (0-99).

## Project layout

| File | Role |
|---|---|
| `main.py` | Command line entry point and the auto-play loop |
| `capture.py` | Window capture with PrintWindow |
| `vision.py` | Board and tray reading |
| `calibrate.py` | Manual layout calibration |
| `solver.py` | Bitboard search and board evaluation |
| `pieces.py` | The piece set |
| `simulator.py`, `benchmark.py` | Headless game and solver benchmark |
| `autoplay.py` | Mouse control with closed-loop dragging |
| `emergency.py` | ESC emergency stop |
| `overlay.py` | Draws suggestions onto the capture |
| `tests/` | Solver and simulator tests (run in CI) |

## Tests

```
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest
```
