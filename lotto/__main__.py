"""Command line: python -m lotto {update,analyze,pick}."""

import argparse
import datetime as dt
import random
import sys
import unicodedata
from pathlib import Path

from . import data, stats
from .generator import TOTAL_COMBINATIONS, generate


def _cell(text, width, left=False):
    """Pad to a terminal width, counting Hangul as two columns."""
    pad = " " * (width - sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text))
    return text + pad if left else pad + text


def cmd_update(args):
    try:
        draws = data.update(args.csv)
    except (OSError, ValueError) as e:
        sys.exit(f"동행복권 서버에서 받아오지 못했습니다: {e}")
    print(f"{draws[-1].no}회({draws[-1].date})까지 {len(draws)}회차 저장 → {args.csv}")


def cmd_analyze(args):
    draws = data.load(args.csv)
    if len(draws) < 100:
        sys.exit("당첨 이력이 부족합니다. 먼저 `python -m lotto update`를 실행하세요.")
    print(f"데이터: {draws[0].no}회({draws[0].date}) ~ {draws[-1].no}회({draws[-1].date}), {len(draws)}회차\n")

    freq = stats.frequencies(draws)
    ranked = sorted(freq, key=freq.get, reverse=True)
    print(f"[번호별 출현 횟수] 기대값 {len(draws) * stats.K / stats.N:.1f}회")
    print("  많이 나온 번호:", ", ".join(f"{n}({freq[n]})" for n in ranked[:6]))
    print("  적게 나온 번호:", ", ".join(f"{n}({freq[n]})" for n in ranked[-6:]))

    stat, p = stats.uniformity_test(draws)
    verdict = "번호 쏠림 의심" if p < 0.01 else "쏠림 근거 없음 (무작위와 구별 안 됨)"
    print(f"\n[균일성 검정] 카이제곱 {stat:.1f} (자유도 {stats.N - 1}), p = {p:.3f} → {verdict}")

    print(f"\n[백테스트] 최근 {args.test_size}회를 직전 이력만으로 예측했을 때 1게임당 성적")
    print("  " + _cell("전략", 10, left=True) + _cell("평균 일치", 10) + _cell("z", 8) + _cell("3개 이상", 10))
    rows = [(name, *stats.backtest(draws, strategy, args.test_size)) for name, strategy in stats.STRATEGIES.items()]
    rows.append(("이론값", stats.EXPECTED_HITS, 0.0, stats.P_THREE_PLUS))
    for name, mean, z, three in rows:
        print("  " + _cell(name, 10, left=True) + _cell(f"{mean:.3f}", 10) + _cell(f"{z:.2f}", 8) + _cell(f"{three:.2%}", 10))
    print("  |z| < 2 이면 무작위로 찍은 것과 차이가 없다는 뜻입니다.")


def cmd_pick(args):
    draws = data.load(args.csv)
    draw_no = args.draw or data.draw_no_on_or_after(dt.date.today())
    rng = random.Random(args.seed) if args.seed is not None else random.SystemRandom()
    past = frozenset(d.numbers for d in draws)
    last_draw = draws[-1].numbers if draws and draws[-1].no == draw_no - 1 else ()

    picks = generate(args.games, rng, past, last_draw)
    print(f"{draw_no}회 ({data.draw_date(draw_no)}) 추천 번호")
    for label, combo in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", picks):
        print(f"  {label}: " + " ".join(f"{n:2d}" for n in combo))
    print(f"\n※ 1등 확률은 어떤 조합이든 1/{TOTAL_COMBINATIONS:,}로 같습니다.")
    print("  생일·연속·등차·용지 패턴 등 사람들이 몰리는 조합을 피해, 당첨 시 나눠 가질 확률을 낮춘 번호입니다.")
    if not last_draw:
        print("  (지난 회차 데이터가 없어 과거 1등·지난 회차 번호 필터는 건너뛰었습니다. `python -m lotto update` 후 다시 실행하세요.)")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m lotto", description="로또 6/45 분석 및 번호 생성")
    parser.add_argument("--csv", type=Path, default=data.DEFAULT_CSV, help="당첨 이력 CSV 경로")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("update", help="동행복권에서 당첨 이력 내려받기").set_defaults(func=cmd_update)

    analyze = sub.add_parser("analyze", help="출현 빈도·균일성 검정·전략 백테스트")
    analyze.add_argument("--test-size", type=int, default=300, help="백테스트할 최근 회차 수")
    analyze.set_defaults(func=cmd_analyze)

    pick = sub.add_parser("pick", help="이번 회차 번호 생성")
    pick.add_argument("--games", type=int, default=5, help="게임 수 (기본 5)")
    pick.add_argument("--draw", type=int, help="회차 (기본: 이번 주 토요일 회차)")
    pick.add_argument("--seed", type=int, help="재현용 난수 시드")
    pick.set_defaults(func=cmd_pick)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
