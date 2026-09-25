"""Benchmark the solver on simulated games.

Usage:
  python benchmark.py                 # 100 games with the default weights
  python benchmark.py --games 20      # quicker
  python benchmark.py --cap 1000      # longer games before stopping

Every game uses a fixed seed, so two runs with the same arguments play
the same pieces and results are directly comparable.
"""

import argparse
import statistics
import time
from dataclasses import asdict
from multiprocessing import Pool

from simulator import play_game
from solver import DEFAULT_WEIGHTS, Weights, solve


def run_game(args: tuple[int, int, dict]) -> tuple[int, int, int, int, float]:
    seed, cap, weight_values = args
    weights = Weights(**weight_values)
    elapsed = 0.0
    calls = 0

    def policy(board, tray, streak):
        nonlocal elapsed, calls
        started = time.perf_counter()
        moves, _ = solve(board, tray, streak, weights=weights)
        elapsed += time.perf_counter() - started
        calls += 1
        return moves

    result = play_game(policy, seed, max_placements=cap)
    return result.placed, result.lines, result.score, result.max_combo, elapsed / max(calls, 1)


def benchmark(weights: Weights, games: int, cap: int, first_seed: int = 0,
              workers: int | None = None) -> dict:
    jobs = [(seed, cap, asdict(weights)) for seed in range(first_seed, first_seed + games)]
    with Pool(workers) as pool:
        results = pool.map(run_game, jobs)
    placed = [r[0] for r in results]
    return {
        "games": games,
        "mean_placed": statistics.mean(placed),
        "median_placed": statistics.median(placed),
        "survived_cap": sum(p >= cap for p in placed),
        "mean_lines": statistics.mean(r[1] for r in results),
        "mean_score": statistics.mean(r[2] for r in results),
        "best_combo": max(r[3] for r in results),
        "ms_per_move": 1000 * statistics.mean(r[4] for r in results),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--cap", type=int, default=500, help="stop a game after this many pieces")
    parser.add_argument("--seed", type=int, default=0, help="first seed")
    args = parser.parse_args()

    started = time.time()
    stats = benchmark(DEFAULT_WEIGHTS, args.games, args.cap, args.seed)
    print(f"{stats['games']} games, cap {args.cap} pieces, {time.time() - started:.0f} s")
    print(f"  pieces placed : mean {stats['mean_placed']:.1f}, median {stats['median_placed']:.0f}, "
          f"reached the cap in {stats['survived_cap']} games")
    print(f"  lines cleared : mean {stats['mean_lines']:.1f}")
    print(f"  score         : mean {stats['mean_score']:.0f}, best combo {stats['best_combo']}")
    print(f"  think time    : {stats['ms_per_move']:.0f} ms per move")


if __name__ == "__main__":
    main()
