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
