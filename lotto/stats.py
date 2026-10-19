"""Frequency statistics and a walk-forward backtest of prediction strategies."""

import math
import random
from collections import Counter
from statistics import fmean

N, K = 45, 6
NUMBERS = range(1, N + 1)

# Matches between any fixed ticket and a fair draw are hypergeometric, so these
# are the numbers a strategy has to beat to show it predicts anything.
EXPECTED_HITS = K * K / N
HITS_VAR = K * (K / N) * ((N - K) / N) * ((N - K) / (N - 1))
P_THREE_PLUS = sum(math.comb(K, h) * math.comb(N - K, K - h) for h in range(3, K + 1)) / math.comb(N, K)


def frequencies(draws) -> dict[int, int]:
    counts = Counter(n for d in draws for n in d.numbers)
    return {n: counts[n] for n in NUMBERS}


def gaps(draws) -> dict[int, int]:
    """Draws since each number last appeared (len(draws) if it never has)."""
    last_seen = dict.fromkeys(NUMBERS, -1)
    for i, d in enumerate(draws):
        for n in d.numbers:
            last_seen[n] = i
    return {n: len(draws) - 1 - i for n, i in last_seen.items()}


def chi2_sf(x: float, k: int) -> float:
    """Upper tail of the chi-square distribution (Wilson-Hilferty approximation)."""
    z = ((x / k) ** (1 / 3) - (1 - 2 / (9 * k))) / math.sqrt(2 / (9 * k))
    return 0.5 * math.erfc(z / math.sqrt(2))


def uniformity_test(draws) -> tuple[float, float]:
    """Chi-square test that every number is equally likely; returns (statistic, p).

    A draw holds 6 distinct numbers, so counts spread less than a multinomial's;
    scaling Pearson's statistic by (N-1)/(N-K) brings it back to chi-square(N-1).
    """
    expected = len(draws) * K / N
    pearson = sum((f - expected) ** 2 / expected for f in frequencies(draws).values())
    stat = pearson * (N - 1) / (N - K)
    return stat, chi2_sf(stat, N - 1)


def _top(scores: dict[int, float], rng: random.Random) -> list[int]:
    ranked = sorted(NUMBERS, key=lambda n: (scores[n], rng.random()), reverse=True)
    return sorted(ranked[:K])


def pick_random(history, rng):
    return sorted(rng.sample(NUMBERS, K))


def pick_hot(history, rng, window=50):
    """The 6 most frequent numbers over the last `window` draws."""
    return _top(frequencies(history[-window:]), rng)


def pick_cold(history, rng):
    """The 6 numbers that have been absent longest ("due" numbers)."""
    return _top(gaps(history), rng)


def pick_weighted(history, rng):
    """Sample without replacement, weighting each number by its all-time frequency."""
    freq = frequencies(history)
    pool, picked = list(NUMBERS), []
    for _ in range(K):
        n = rng.choices(pool, weights=[freq[m] + 1 for m in pool])[0]
        pool.remove(n)
        picked.append(n)
    return sorted(picked)


STRATEGIES = {
    "random": pick_random,
    "hot": pick_hot,
    "cold": pick_cold,
    "weighted": pick_weighted,
}


def backtest(draws, strategy, test_size=300, seed=0):
    """Walk forward over the last `test_size` draws, predicting each from the ones before it.

    Returns (mean hits per ticket, z-score against EXPECTED_HITS, share of tickets with 3+ hits).
    """
    rng = random.Random(seed)
    start = max(1, len(draws) - test_size)
    hits = [len(set(strategy(draws[:i], rng)) & set(draws[i].numbers)) for i in range(start, len(draws))]
    mean = fmean(hits)
    z = (mean - EXPECTED_HITS) / math.sqrt(HITS_VAR / len(hits))
    return mean, z, sum(h >= 3 for h in hits) / len(hits)
