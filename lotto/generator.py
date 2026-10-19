"""Pick combinations that other players are unlikely to choose.

Every combination wins with the same probability (1 in 8,145,060), so no choice
of numbers raises the chance of winning. What a choice does change is how many
people split the prize: players over-pick birthdays, runs, number patterns,
shapes on the slip and last week's numbers. Rejecting those combinations from a
uniform draw keeps the odds intact while lowering the expected number of co-winners.
"""

import math
import random
from collections import Counter

from .stats import K, N, NUMBERS

SLIP_WIDTH = 7  # the Lotto 6/45 slip lays numbers out in rows of 7
TOTAL_COMBINATIONS = math.comb(N, K)


def longest_run(combo) -> int:
    best = run = 1
    for a, b in zip(combo, combo[1:]):
        run = run + 1 if b == a + 1 else 1
        best = max(best, run)
    return best


def longest_progression(combo) -> int:
    """Length of the longest arithmetic progression inside a sorted combination."""
    members = set(combo)
    best = 2
    for i, a in enumerate(combo):
        for b in combo[i + 1:]:
            step, length, x = b - a, 2, b
            while x + step in members:
                x += step
                length += 1
            best = max(best, length)
    return best


def popularity_flags(combo, past=frozenset(), last_draw=()) -> list[str]:
    """Reasons a sorted combination looks like a common human pick (empty if none)."""
    flags = []
    if sum(n > 31 for n in combo) < 2:
        flags.append("31 이하(생일) 숫자 위주")
    if longest_run(combo) >= 3:
        flags.append("연속 번호 3개 이상")
    if longest_progression(combo) >= 4:
        flags.append("등차수열 4개 이상")
    rows = Counter((n - 1) // SLIP_WIDTH for n in combo)
    cols = Counter((n - 1) % SLIP_WIDTH for n in combo)
    if max(rows.values()) >= 4 or max(cols.values()) >= 4:
        flags.append("용지 한 줄에 4개 이상")
    if tuple(combo) in past:
        flags.append("과거 1등 조합")
    if len(set(combo) & set(last_draw)) >= 3:
        flags.append("지난 회차 번호 3개 이상")
    return flags


def generate(games=5, rng=None, past=frozenset(), last_draw=(), max_overlap=2, avoid=(), max_tries=1_000_000):
    """Draw `games` unflagged combinations sharing at most `max_overlap` numbers
    with each other and with every line in `avoid` (tickets already bought)."""
    rng = rng or random.SystemRandom()
    picks = []
    for _ in range(max_tries):
        if len(picks) == games:
            return picks
        combo = tuple(sorted(rng.sample(NUMBERS, K)))
        if popularity_flags(combo, past, last_draw):
            continue
        if any(len(set(combo) & set(p)) > max_overlap for p in (*avoid, *picks)):
            continue
        picks.append(combo)
    raise ValueError(f"could not find {games} combinations; lower games or raise max_overlap")


def overlap_bound_rate(lines, max_overlap=2, samples=200_000, seed=0) -> float:
    """Estimated share of all combinations sharing at most `max_overlap` numbers with every line.

    Equivalently, the chance that a fair draw leaves each line with `max_overlap` hits or fewer.
    """
    rng = random.Random(seed)
    masks = [sum(1 << n for n in line) for line in lines]
    ok = 0
    for _ in range(samples):
        draw = sum(1 << n for n in rng.sample(NUMBERS, K))
        ok += all((draw & m).bit_count() <= max_overlap for m in masks)
    return ok / samples


def pass_rate(samples=200_000, seed=0) -> float:
    """Estimated share of all combinations that raise no popularity flag."""
    rng = random.Random(seed)
    ok = sum(not popularity_flags(tuple(sorted(rng.sample(NUMBERS, K)))) for _ in range(samples))
    return ok / samples
