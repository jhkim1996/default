import argparse
import datetime as dt
import random
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from lotto import data, prizes, stats, theory
from lotto.__main__ import _line
from lotto.generator import (
    generate,
    least_and_middle,
    longest_progression,
    longest_run,
    overlap_bound_rate,
    popularity_flags,
    simulate_auto,
)


def simulated_draws(count, seed=1):
    """Fair draws, for checking the statistics behave as theory says they should."""
    rng = random.Random(seed)
    return [
        data.Draw(no, data.draw_date(no), tuple(sorted(rng.sample(stats.NUMBERS, 6))), rng.randint(1, 45))
        for no in range(1, count + 1)
    ]


class DrawCalendarTest(unittest.TestCase):
    def test_draw_numbers_follow_saturdays(self):
        self.assertEqual(data.draw_no_on_or_after(dt.date(2002, 12, 7)), 1)
        self.assertEqual(data.draw_date(1000), dt.date(2022, 1, 29))
        self.assertEqual(data.draw_no_on_or_after(dt.date(2026, 10, 19)), 1247)
        self.assertEqual(data.draw_no_on_or_after(dt.date(2026, 10, 24)), 1247)
        self.assertEqual(data.draw_no_on_or_after(dt.date(2026, 10, 25)), 1248)


class DataTest(unittest.TestCase):
    def test_parse_api(self):
        payload = {
            "returnValue": "success", "drwNo": 1, "drwNoDate": "2002-12-07",
            "drwtNo1": 10, "drwtNo2": 23, "drwtNo3": 29, "drwtNo4": 33, "drwtNo5": 37, "drwtNo6": 40,
            "bnusNo": 16,
        }
        self.assertEqual(data.parse_api(payload), data.Draw(1, dt.date(2002, 12, 7), (10, 23, 29, 33, 37, 40), 16))
        self.assertIsNone(data.parse_api({"returnValue": "fail"}))

    def test_recent_draws(self):
        self.assertEqual(data.RECENT[-1].date, dt.date(2026, 11, 14))
        self.assertEqual([d.no for d in data.RECENT], list(range(1229, 1251)))
        for d in data.RECENT:
            self.assertEqual(len(set(d.numbers)), 6)
            self.assertEqual(list(d.numbers), sorted(d.numbers))
            self.assertNotIn(d.bonus, d.numbers)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(data.history(Path(tmp) / "missing.csv"), data.RECENT)

    def test_csv_round_trip(self):
        draws = simulated_draws(5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draws.csv"
            data.save(list(reversed(draws)), path)
            self.assertEqual(data.load(path), draws)


class StatsTest(unittest.TestCase):
    def test_gaps(self):
        draws = simulated_draws(30)
        gaps = stats.gaps(draws)
        for n in draws[-1].numbers:
            self.assertEqual(gaps[n], 0)

    def test_fair_draws_pass_uniformity_test(self):
        _, p = stats.uniformity_test(simulated_draws(2000))
        self.assertGreater(p, 0.01)

    def test_strategies_do_not_beat_fair_draws(self):
        draws = simulated_draws(600)
        for name, strategy in stats.STRATEGIES.items():
            mean, z, _ = stats.backtest(draws, strategy, test_size=300)
            self.assertLess(abs(z), 4, name)


class GeneratorTest(unittest.TestCase):
    def test_pattern_helpers(self):
        self.assertEqual(longest_run((3, 4, 5, 20, 30, 31)), 3)
        self.assertEqual(longest_progression((5, 10, 15, 20, 33, 41)), 4)

    def test_flags_popular_combinations(self):
        self.assertTrue(popularity_flags((1, 2, 3, 4, 5, 6)))
        self.assertTrue(popularity_flags((3, 9, 12, 18, 25, 28)))   # all birthdays
        self.assertTrue(popularity_flags((4, 11, 18, 25, 33, 40)))  # one column of the slip
        self.assertTrue(popularity_flags((2, 9, 19, 33, 38, 44), past={(2, 9, 19, 33, 38, 44)}))
        self.assertTrue(popularity_flags((2, 9, 19, 33, 38, 44), last_draw=(2, 9, 19, 20, 21, 22)))
        self.assertEqual(popularity_flags((2, 9, 19, 33, 38, 44)), [])

    def test_generate(self):
        picks = generate(10, random.Random(7))
        self.assertEqual(len(picks), 10)
        for i, combo in enumerate(picks):
            self.assertEqual(list(combo), sorted(set(combo)))
            self.assertEqual(popularity_flags(combo), [])
            for other in picks[:i]:
                self.assertLessEqual(len(set(combo) & set(other)), 2)

    def test_generate_avoids_bought_lines(self):
        bought = generate(10, random.Random(3))
        third = generate(5, random.Random(4), avoid=bought)
        for combo in third:
            for line in bought:
                self.assertLessEqual(len(set(combo) & set(line)), 2)

    def test_overlap_bound_rate_matches_hypergeometric(self):
        # One line keeps <= 2 hits unless it wins 5th prize or better.
        rate = overlap_bound_rate([(2, 9, 19, 33, 38, 44)], samples=100_000)
        self.assertAlmostEqual(rate, 1 - stats.P_THREE_PLUS, delta=0.003)
        self.assertEqual(overlap_bound_rate([(1, 2, 3, 4, 5, 6)], max_overlap=6, samples=1000), 1.0)

    def test_parse_line(self):
        self.assertEqual(_line("40,5 14 27 29 32"), (5, 14, 27, 29, 32, 40))
        for bad in ("1 2 3 4 5", "1 1 2 3 4 5", "0 2 3 4 5 6", "2 3 4 5 6 46"):
            with self.assertRaises(argparse.ArgumentTypeError):
                _line(bad)

    def test_least_and_middle(self):
        counts = simulate_auto(1000, rng=random.Random(5))
        self.assertEqual(sum(counts.values()), 1000 * 5 * 6)
        least, middle = least_and_middle(counts, random.Random(6))
        ranked = sorted(counts.values())
        self.assertEqual(sorted(counts[n] for n in least), ranked[:4])
        self.assertEqual(sorted(counts[n] for n in middle), ranked[21:23])


class PrizesTest(unittest.TestCase):
    def test_tier_ways_cover_three_or_more_matches(self):
        self.assertEqual(prizes.TIER_WAYS, (1, 6, 228, 11115, 182780))
        self.assertAlmostEqual(sum(prizes.TIER_WAYS) / prizes.TOTAL, stats.P_THREE_PLUS)

    def test_exact_expectation_matches_itself(self):
        games = 100_000_000
        row = tuple(games * w / prizes.TOTAL for w in prizes.TIER_WAYS)
        self.assertAlmostEqual(prizes.games_sold(row), games)
        for observed, expected in prizes.compare([row]):
            self.assertAlmostEqual(observed / expected, 1)

    def test_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prizes.csv"
            self.assertEqual(prizes.load(path), prizes.RECENT)
            path.write_text(",".join(prizes.FIELDS) + "\n1,2,3,4,5,1,0,0\n", encoding="utf-8")
            self.assertEqual(prizes.load(path), [(1, 2, 3, 4, 5, 1, 0, 0)])
        for row in prizes.RECENT:
            self.assertEqual(row[0], sum(row[5:]))


class TheoryTest(unittest.TestCase):
    def test_unbought_combinations(self):
        self.assertEqual(theory.unbought_combinations(0, 0.77), prizes.TOTAL)
        # 1.2억 games, 77% auto: about 11 auto tickets per combination, so ~100 get none.
        self.assertTrue(50 < theory.unbought_combinations(1.2e8, 0.77) < 150)

    def test_overlap_and_birthday_share(self):
        draws = [data.Draw(no, data.draw_date(no), nums, 45) for no, nums in
                 [(1, (1, 2, 3, 32, 33, 34)), (2, (1, 2, 35, 36, 37, 38)), (3, (4, 5, 6, 7, 8, 9))]]
        self.assertEqual(theory.consecutive_overlap(draws), 1.0)
        self.assertAlmostEqual(theory.birthday_share(draws), 11 / 18)
        # Fair draws share about 0.8 numbers with the next one.
        self.assertAlmostEqual(theory.consecutive_overlap(simulated_draws(3000)), theory.EXPECTED_OVERLAP, delta=0.05)

    def test_hot_lines(self):
        window = data.RECENT[-10:]
        lines, freq = theory.hot_lines(window, rng=random.Random(1))
        self.assertEqual(len(set(lines)), 5)
        for line in lines:
            self.assertEqual(list(line), sorted(set(line)))
            self.assertTrue(all(freq[n] > 0 for n in line))  # only numbers drawn lately
        # Weighted: the most drawn number comes up far more than one drawn once.
        hot = max(freq, key=freq.get)
        once = next(n for n in freq if freq[n] == 1)
        self.assertGreaterEqual(freq[hot], 4)
        rng = random.Random(2)
        counts = Counter(n for _ in range(200) for line in theory.hot_lines(window, rng=rng)[0] for n in line)
        self.assertGreater(counts[hot], 2 * counts[once])
        # Different presses give different sheets.
        self.assertNotEqual(theory.hot_lines(window, rng=random.Random(3))[0],
                            theory.hot_lines(window, rng=random.Random(4))[0])
        with self.assertRaises(ValueError):
            theory.hot_lines(data.RECENT[-1:], max_tries=100)

    def test_backtest(self):
        results = theory.backtest(data.RECENT, window=10, weeks=12, sheets=20)
        self.assertEqual([d.no for d, _ in results], list(range(1239, 1251)))
        self.assertTrue(all(sum(hits.values()) == 100 for _, hits in results))
        # On fair draws no way of picking beats 0.8 matches per line in the long run.
        fair = theory.backtest(simulated_draws(130, seed=5), window=10, weeks=120, sheets=20)
        mean = sum(theory.mean_hits(h) for _, h in fair) / len(fair)
        self.assertAlmostEqual(mean, stats.EXPECTED_HITS, delta=0.1)

if __name__ == "__main__":
    unittest.main()
