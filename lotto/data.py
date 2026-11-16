"""Lotto 6/45 draw history: download from dhlottery.co.kr and cache as CSV."""

import csv
import datetime as dt
import json
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

API_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={}"
FIRST_DRAW = dt.date(2002, 12, 7)  # draw 1; one draw every Saturday since
# A PyInstaller build unpacks into a temporary folder, so keep its data next to the executable.
_BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
DATA_DIR = _BASE / "data"
DEFAULT_CSV = DATA_DIR / "draws.csv"
FIELDS = ["draw", "date", "n1", "n2", "n3", "n4", "n5", "n6", "bonus"]


@dataclass(frozen=True)
class Draw:
    no: int
    date: dt.date
    numbers: tuple[int, ...]
    bonus: int


# Most recent draws as reported in the news, so the tools work before `update` has run.
RECENT = [
    Draw(no, FIRST_DRAW + dt.timedelta(weeks=no - 1), numbers, bonus)
    for no, numbers, bonus in [
        (1229, (12, 13, 29, 34, 37, 42), 16),
        (1230, (3, 8, 9, 22, 28, 42), 45),
        (1231, (4, 13, 14, 18, 31, 38), 15),
        (1232, (12, 15, 19, 22, 24, 36), 3),
        (1233, (2, 7, 20, 25, 37, 40), 29),
        (1234, (1, 15, 19, 31, 35, 43), 27),
        (1235, (6, 7, 11, 15, 39, 43), 20),
        (1236, (12, 18, 21, 29, 34, 38), 10),
        (1237, (10, 20, 23, 34, 37, 40), 36),
        (1238, (2, 13, 18, 32, 38, 42), 22),
        (1239, (11, 13, 22, 32, 33, 36), 8),
        (1240, (11, 13, 19, 20, 31, 44), 27),
        (1241, (7, 13, 16, 23, 24, 43), 9),
        (1242, (2, 4, 10, 16, 31, 41), 9),
        (1243, (9, 18, 24, 38, 43, 44), 35),
        (1244, (1, 13, 18, 26, 34, 38), 25),
        (1245, (4, 5, 25, 28, 32, 42), 12),
        (1246, (16, 22, 23, 24, 27, 28), 6),
        (1247, (8, 14, 21, 22, 42, 45), 24),
        (1248, (16, 18, 27, 36, 38, 42), 22),
        (1249, (2, 11, 16, 25, 34, 35), 14),
        (1250, (1, 5, 18, 23, 27, 28), 8),
    ]
]


def draw_date(no: int) -> dt.date:
    return FIRST_DRAW + dt.timedelta(weeks=no - 1)


def draw_no_on_or_after(day: dt.date) -> int:
    """Number of the first draw held on or after `day`."""
    saturday = day + dt.timedelta(days=(5 - day.weekday()) % 7)
    return (saturday - FIRST_DRAW).days // 7 + 1


def parse_api(payload: dict) -> Draw | None:
    """Turn a getLottoNumber response into a Draw, or None for an undrawn round."""
    if payload.get("returnValue") != "success":
        return None
    return Draw(
        no=int(payload["drwNo"]),
        date=dt.date.fromisoformat(payload["drwNoDate"]),
        numbers=tuple(sorted(int(payload[f"drwtNo{i}"]) for i in range(1, 7))),
        bonus=int(payload["bnusNo"]),
    )


def fetch_draw(no: int, timeout: float = 10) -> Draw | None:
    req = urllib.request.Request(API_URL.format(no), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return parse_api(json.load(resp))


def load(path: Path = DEFAULT_CSV) -> list[Draw]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        draws = [
            Draw(
                no=int(row["draw"]),
                date=dt.date.fromisoformat(row["date"]),
                numbers=tuple(sorted(int(row[f"n{i}"]) for i in range(1, 7))),
                bonus=int(row["bonus"]),
            )
            for row in csv.DictReader(f)
        ]
    return sorted(draws, key=lambda d: d.no)


def history(path: Path = DEFAULT_CSV) -> list[Draw]:
    """Cached draws, or the built-in RECENT ones when nothing has been downloaded."""
    return load(path) or RECENT


def save(draws: list[Draw], path: Path = DEFAULT_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        for d in sorted(draws, key=lambda d: d.no):
            writer.writerow([d.no, d.date.isoformat(), *d.numbers, d.bonus])


def update(path: Path = DEFAULT_CSV, delay: float = 0.2) -> list[Draw]:
    """Fetch every draw newer than the cached ones and rewrite the cache."""
    draws = load(path)
    no = draws[-1].no + 1 if draws else 1
    latest = draw_no_on_or_after(dt.date.today())
    while no <= latest and (draw := fetch_draw(no)) is not None:
        draws.append(draw)
        if no % 100 == 0:
            save(draws, path)  # keep progress if a long first download is interrupted
        no += 1
        time.sleep(delay)
    save(draws, path)
    return draws
