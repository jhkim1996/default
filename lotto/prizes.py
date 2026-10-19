"""Winners per prize tier: what draws produced versus what a random combination should.

For any winning combination, a ticket bought at random lands in each tier with a
fixed probability, so tier counts are set by how many games were sold. Only the
1st tier depends noticeably on the combination itself: patterns that many people
pick by hand collect far more identical tickets than a typical combination.
"""

import csv
import math
from pathlib import Path

from .data import DATA_DIR
from .stats import K, N

TOTAL = math.comb(N, K)
# Ticket combinations falling in each tier, out of TOTAL, for a draw of 6 numbers + bonus.
TIER_WAYS = (
    1,                                      # 1st: all 6
    K,                                      # 2nd: 5 + bonus
    K * (N - K - 1),                        # 3rd: 5, not the bonus
    math.comb(K, 4) * math.comb(N - K, 2),  # 4th: 4
    math.comb(K, 3) * math.comb(N - K, 3),  # 5th: 3
)

DEFAULT_PRIZES = DATA_DIR / "prizes.csv"
FIELDS = ["first", "second", "third", "fourth", "fifth", "auto", "manual", "semi_auto"]

# Winners per tier, then the 1st-prize split by auto/manual/semi-auto ticket,
# for five recent draws as shown on dhlottery result pages.
RECENT = [
    (16, 64, 3350, 155108, 2608922, 11, 4, 1),
    (10, 91, 3102, 163177, 2786728, 10, 0, 0),
    (18, 80, 3731, 179216, 2848954, 11, 7, 0),
    (12, 115, 3591, 174306, 2853501, 10, 2, 0),
    (9, 104, 3206, 165377, 2729145, 8, 1, 0),
]


def load(path: Path = DEFAULT_PRIZES) -> list[tuple[int, ...]]:
    """Prize rows from a CSV with FIELDS columns, or RECENT if there is none."""
    if not path.exists():
        return RECENT
    with path.open(newline="", encoding="utf-8") as f:
        return [tuple(int(row[k]) for k in FIELDS) for row in csv.DictReader(f)]


def games_sold(row) -> float:
    """Poisson maximum-likelihood estimate of games sold in a draw, from its tier counts."""
    return sum(row[:5]) * TOTAL / sum(TIER_WAYS)


def compare(rows) -> list[tuple[float, float]]:
    """Per tier, (mean winners observed, mean winners expected for a random combination)."""
    expected = [[games_sold(r) * ways / TOTAL for ways in TIER_WAYS] for r in rows]
    return [
        (sum(r[t] for r in rows) / len(rows), sum(e[t] for e in expected) / len(rows))
        for t in range(len(TIER_WAYS))
    ]
