"""Command line: python -m lotto {update,analyze,pick,plan,sim,ratio}."""

import argparse
import datetime as dt
import random
import sys
import unicodedata
from pathlib import Path

from . import data, prizes, stats
from .generator import TOTAL_COMBINATIONS, generate, least_and_middle, overlap_bound_rate, simulate_auto


def _cell(text, width, left=False):
    """Pad to a terminal width, counting Hangul as two columns."""
    pad = " " * (width - sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text))
    return text + pad if left else pad + text


def _line(text):
    """Parse a bought line such as "5 14 27 29 32 40" or "5,14,27,29,32,40"."""
    numbers = sorted({int(t) for t in text.replace(",", " ").split()})
    if len(numbers) != stats.K or not all(1 <= n <= stats.N for n in numbers):
        raise argparse.ArgumentTypeError(f"1~45 사이 서로 다른 숫자 6개가 필요합니다: {text!r}")
    return tuple(numbers)


def _context(args):
    """Draw number, RNG and the history-based filters shared by pick and plan."""
    draws = data.load(args.csv)
    draw_no = args.draw or data.draw_no_on_or_after(dt.date.today())
    rng = random.Random(args.seed) if args.seed is not None else random.SystemRandom()
    past = frozenset(d.numbers for d in draws)
    last_draw = draws[-1].numbers if draws and draws[-1].no == draw_no - 1 else ()
    return draw_no, rng, past, last_draw


def _print_sheet(title, lines):
    print(title)
    for label, combo in zip("ABCDE", lines):
        print(f"  {label}: " + " ".join(f"{n:2d}" for n in combo))


def _print_missing_history(last_draw):
    if not last_draw:
        print("  (지난 회차 데이터가 없어 과거 1등·지난 회차 번호 필터는 건너뛰었습니다. `update` 명령으로 당첨 이력을 받은 뒤 다시 실행하세요.)")


def cmd_update(args):
    try:
        draws = data.update(args.csv)
    except (OSError, ValueError) as e:
        sys.exit(f"동행복권 서버에서 받아오지 못했습니다: {e}")
    print(f"{draws[-1].no}회({draws[-1].date})까지 {len(draws)}회차 저장 → {args.csv}")


def cmd_analyze(args):
    draws = data.load(args.csv)
    if len(draws) < 100:
        sys.exit("당첨 이력이 부족합니다. 먼저 `update` 명령으로 당첨 이력을 받으세요.")
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
    draw_no, rng, past, last_draw = _context(args)
    picks = generate(args.games, rng, past, last_draw)
    print(f"{draw_no}회 ({data.draw_date(draw_no)}) 추천 번호")
    for label, combo in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", picks):
        print(f"  {label}: " + " ".join(f"{n:2d}" for n in combo))
    print(f"\n※ 1등 확률은 어떤 조합이든 1/{TOTAL_COMBINATIONS:,}로 같습니다.")
    print("  생일·연속·등차·용지 패턴 등 사람들이 몰리는 조합을 피해, 당첨 시 나눠 가질 확률을 낮춘 번호입니다.")
    _print_missing_history(last_draw)


def cmd_plan(args):
    """Tickets 1-2 first; ticket 3 only from combinations left if no earlier line hits 3+."""
    draw_no, rng, past, last_draw = _context(args)
    bought = args.line or generate(10, rng, past, last_draw)
    third = generate(5, rng, past, last_draw, avoid=bought)

    print(f"{draw_no}회 ({data.draw_date(draw_no)}) 3장 구매 계획\n")
    sheets = [bought[i:i + 5] for i in range(0, len(bought), 5)]
    for i, sheet in enumerate(sheets, 1):
        _print_sheet(f"{i}장{' (입력한 번호)' if args.line else ''}", sheet)
    _print_sheet(f"{len(sheets) + 1}장 (앞 {len(bought)}줄과 각각 2개 이하로만 겹치는 번호)", third)

    rate = overlap_bound_rate(bought)
    remaining = rate * TOTAL_COMBINATIONS
    print(f"\n[가정] 앞의 {len(bought)}줄이 모두 2개 이하로 맞는다")
    print(f"  가정이 맞을 확률:          약 {rate:.1%}  (1등 후보가 약 {remaining:,.0f}개 조합으로 줄어듦)")
    print(f"  가정이 맞을 때 마지막 장 1줄의 1등 확률: 약 1/{remaining:,.0f}")
    print(f"  가정이 틀릴 확률:          약 {1 - rate:.1%}  → 앞 장에서 3개 이상(5등 이상) 당첨, 마지막 장 1등은 불가")
    print(f"  두 경우를 합치면 마지막 장 1줄의 1등 확률: {rate:.1%} × 1/{remaining:,.0f} = 1/{TOTAL_COMBINATIONS:,} (변화 없음)")
    print(f"  → 1등 확률은 {len(bought) + len(third)}줄 × 1/{TOTAL_COMBINATIONS:,}. 대신 줄끼리 번호가 덜 겹쳐 고르게 퍼집니다.")
    _print_missing_history(last_draw)


def cmd_sim(args):
    """One line per round: simulate auto tickets, take the 4 least-drawn and 2 middle numbers."""
    draw_no, rng, _, _ = _context(args)
    print(f"{draw_no}회 ({data.draw_date(draw_no)}) 줄마다 자동 {args.sheets:,}장 ({args.sheets * 5:,}줄) 새로 시뮬레이션")
    print(f"  번호당 평균 {args.sheets * 5 * stats.K / stats.N:.1f}회 · 중간 = 45개를 횟수 순으로 세웠을 때 22·23번째\n")
    lines = []
    while len(lines) < 5:
        counts = simulate_auto(args.sheets, rng=rng)
        least, middle = least_and_middle(counts, rng)
        line = tuple(sorted(least + middle))
        if line in lines:
            continue  # vanishingly rare; simulate this round again
        lines.append(line)
        print(f"  {len(lines)}번째 시뮬레이션 → 적게: " + ", ".join(f"{n}({counts[n]})" for n in least)
              + "  중간: " + ", ".join(f"{n}({counts[n]})" for n in middle))
    print()
    _print_sheet("5,000원 1장", lines)
    print(f"\n※ 자동 번호는 균등 무작위라 시뮬레이션의 많고 적음은 우연이며, 각 줄의 1등 확률은 1/{TOTAL_COMBINATIONS:,}로 같습니다.")


def cmd_ratio(args):
    """Check recent prize tables against random expectation, then pick combinations that fit them."""
    rows = prizes.load(args.prizes)
    draw_no, rng, past, last_draw = _context(args)
    games = sum(prizes.games_sold(r) for r in rows) / len(rows)
    auto, first = sum(r[5] for r in rows), sum(r[0] for r in rows)

    print(f"[최근 {len(rows)}회 당첨 결과] 판매량 추정: 회당 약 {games / 1e8:.2f}억 게임 (등수별 당첨자 수로 역산)\n")
    print("  " + _cell("등수", 6, left=True) + _cell("평균 당첨자", 14) + _cell("무작위 조합 기대값", 20) + _cell("관측/기대", 11))
    comparison = prizes.compare(rows)
    for tier, (observed, expected) in enumerate(comparison, 1):
        print("  " + _cell(f"{tier}등", 6, left=True) + _cell(f"{observed:,.1f}", 14)
              + _cell(f"{expected:,.1f}", 20) + _cell(f"{observed / expected:.2f}", 11))
    ratio = " : ".join(f"{w:,}" for w in prizes.TIER_WAYS)
    print(f"\n  1등 당첨 {first}게임 중 자동 {auto}게임 ({auto / first:.0%})")
    print(f"  → 1~5등 비율은 당첨번호와 상관없이 {ratio} × 판매량으로 정해집니다.")
    first_observed, first_expected = comparison[0]
    if first_observed < first_expected:
        print(f"    1등이 {first_observed / first_expected:.2f}배인 건 수동 구매가 일부 조합에 몰리기 때문으로, 그런 조합은 1등이 평소보다 훨씬 많이 나옵니다.")
    print("    그래서 사람들이 많이 고르는 패턴(생일·연속·등차·용지 모양)을 뺀 조합으로 골랐습니다.\n")

    _print_sheet(f"{draw_no}회 ({data.draw_date(draw_no)}) 5,000원 1장", generate(5, rng, past, last_draw))
    print(f"\n※ 각 줄의 1등 확률은 1/{TOTAL_COMBINATIONS:,}로 같습니다.")
    _print_missing_history(last_draw)


def main(argv=None):
    # Piped output on Windows goes through the ANSI code page, which may lack Hangul.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

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

    plan = sub.add_parser("plan", help="2장 산 뒤 '줄마다 2개 이하' 가정으로 3장째 번호 고르기")
    plan.add_argument("--line", type=_line, action="append", help='이미 산 번호 한 줄 (예: --line "5 14 27 29 32 40"), 여러 번 지정')
    plan.add_argument("--draw", type=int, help="회차 (기본: 이번 주 토요일 회차)")
    plan.add_argument("--seed", type=int, help="재현용 난수 시드")
    plan.set_defaults(func=cmd_plan)

    sim = sub.add_parser("sim", help="줄마다 자동 구매 시뮬레이션: 최소 빈도 4개 + 중간 빈도 2개로 1장")
    sim.add_argument("--sheets", type=int, default=1000, help="줄마다 시뮬레이션할 자동 구매 장 수 (기본 1000)")
    sim.add_argument("--draw", type=int, help="회차 (기본: 이번 주 토요일 회차)")
    sim.add_argument("--seed", type=int, help="재현용 난수 시드")
    sim.set_defaults(func=cmd_sim)

    ratio = sub.add_parser("ratio", help="최근 1~5등 당첨자 비율 분석 + 그 비율에 맞는 1장")
    ratio.add_argument("--prizes", type=Path, default=prizes.DEFAULT_PRIZES, help="등수별 당첨자 수 CSV (없으면 내장된 최근 5회)")
    ratio.add_argument("--draw", type=int, help="회차 (기본: 이번 주 토요일 회차)")
    ratio.add_argument("--seed", type=int, help="재현용 난수 시드")
    ratio.set_defaults(func=cmd_ratio)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
