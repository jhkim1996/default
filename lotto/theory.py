"""Test the idea that the 1st-prize numbers are chosen from what buyers picked.

Two readings of the idea, and what each would show:
- the least-bought combination wins: with ~100M games, most of them random auto
  picks, some combinations always go unbought, so 1st prize would have no winners;
- the 6 least-picked numbers win: auto picks spread evenly over the numbers, so
  manual buyers' steady habits set the ranking, the same numbers would come up
  week after week, and the birthday numbers 1-31 people favour would rarely appear.
If the second reading held, the numbers drawn most often lately are the ones to buy.
"""

import itertools
import math
import random

from . import prizes
from .stats import EXPECTED_HITS, K, N, NUMBERS, frequencies

EXPECTED_OVERLAP = EXPECTED_HITS  # numbers two independent draws share, on average
BIRTHDAY_SHARE = 31 / N           # share of drawn numbers that are 1-31 when draws are fair


def unbought_combinations(games: float, auto_share: float) -> float:
    """Expected combinations that no auto ticket picked, out of all C(45, 6)."""
    return prizes.TOTAL * math.exp(-games * auto_share / prizes.TOTAL)


def consecutive_overlap(draws) -> float:
    """Mean count of numbers shared by each draw and the one after it."""
    pairs = list(zip(draws, draws[1:]))
    return sum(len(set(a.numbers) & set(b.numbers)) for a, b in pairs) / len(pairs)


def birthday_share(draws) -> float:
    return sum(n <= 31 for d in draws for n in d.numbers) / (K * len(draws))


def hot_lines(draws, games=5, rng=None):
    """Lines built from the most frequently drawn numbers, best total frequency first.

    Combinations of the 10 most frequent numbers are ranked by how often their
    numbers were drawn; ties are broken at random. Returns (lines, frequencies).
    """
    rng = rng or random.SystemRandom()
    freq = frequencies(draws)
    pool = sorted(NUMBERS, key=lambda n: (-freq[n], rng.random()))[:K + 4]
    combos = sorted(itertools.combinations(pool, K), key=lambda c: (-sum(freq[n] for n in c), rng.random()))
    return [tuple(sorted(c)) for c in combos[:games]], freq
