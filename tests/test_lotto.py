import argparse
import datetime as dt
import random
import tempfile
import unittest
from pathlib import Path

from lotto import data, stats
from lotto.__main__ import _line
from lotto.generator import generate, longest_progression, longest_run, overlap_bound_rate, popularity_flags


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


if __name__ == "__main__":
    unittest.main()
