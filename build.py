"""Build everything from the shipped (masked) data: metrics, engine demo, README numbers, dist/.

Usage:
  python3 build.py           # write data/metrics.json, README numbers block, dist/
  python3 build.py --check   # exit 1 if the README numbers block is out of date
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from audit.agreement import agreement, load_author
from audit.classify import classify
from audit.metrics import compute
from audit.validate import load_rows, score
from engine.settlement import replay
from engine.simulate import simulate

ROOT = Path(__file__).parent
DATA, DIST = ROOT / "data", ROOT / "dist"
TODAY = date(2026, 10, 22)
START, END = "<!-- METRICS:START -->", "<!-- METRICS:END -->"
APP_NAMES = {"cars24": "Cars24", "carinfo": "CarInfo", "vehicleinfo": "VehicleInfo"}


def build_metrics() -> dict:
    rows = load_rows(DATA / "validation.csv")
    m = compute(json.loads((DATA / "reviews.json").read_text()),
                json.loads((DATA / "base_counts.json").read_text()),
                {"dev": score(rows, "dev"), "test": score(rows, "test")}, rows)
    author_file = DATA / "author_labels.csv"
    if author_file.exists():
        author = load_author(author_file)
        m["author_check"] = {"vs_sample": agreement(author, {r["id"]: r["labels"] for r in rows}),
                             "vs_rules": agreement(author, {r["id"]: classify(r["text"]) for r in rows})}
    return m


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _ci(ci: list) -> str:
    return f"{_pct(ci[0])} to {_pct(ci[1])}"


def render_readme_table(m: dict) -> str:
    s, rep, val, q = m["sample_estimates"], m["replies"], m["validation"]["test"], m["q3_vs_q2"]
    per_app = ", ".join(f"{APP_NAMES[a]} {n:,}" for a, n in sorted(m["challan_reviews"].items()))
    low = ", ".join(f"{APP_NAMES[a]} {n:,}" for a, n in sorted(m["low_star_total"].items()))

    def est(t: str, label: str) -> str:
        e, o = s["types"][t], m["estimates"][t]["observed"]
        return (f"| {label} | about {e['scaled']:,} reviews (95% CI {e['scaled_ci'][0]:,} to {e['scaled_ci'][1]:,}); "
                f"{e['k']} of {s['n']} in the labelled sample; keyword rules flag {o:,} | "
                f"`metrics.sample_estimates.types.{t}` |")

    rows = [
        "| What | Number | Source |",
        "|---|---|---|",
        f"| 1-2 star Play reviews read ({m['window'][0]} to {m['window'][1]}) | {sum(m['low_star_total'].values()):,} ({low}) | `metrics.low_star_total` |",
        f"| Of those, about challans | {sum(m['challan_reviews'].values()):,} ({per_app}) | `metrics.challan_reviews` |",
        f"| Of those, written after Cars24 owned the app | {sum(m['since_acquisition']['challan_reviews'].values()):,} "
        f"({', '.join(f'{APP_NAMES[a]} {n:,}' for a, n in sorted(m['since_acquisition']['challan_reviews'].items()))}; "
        f"CarInfo from {m['since_acquisition']['dates']['carinfo']}, VehicleInfo from {m['since_acquisition']['dates']['vehicleinfo']}) | `metrics.since_acquisition` |",
        f"| Challan-failure reviews as a share of all 1-2 star reviews, 2026 Q2 to Q3 | {_pct(q['share_q2'])} to {_pct(q['share_q3'])} "
        f"(keyword rules flag {q['2026Q2']} then {q['2026Q3']}; all 1-2 star reviews also rose, {q['low_star_q2']:,} to {q['low_star_q3']:,}) | `metrics.q3_vs_q2` |",
        f"| Failures within Cars24's and its payment partner's control, based on how users describe them | {_pct(s['control']['in_control']['share'])} "
        f"(95% CI {_ci(s['control']['in_control']['ci'])}) of {s['failure_reviews']} failure reviews in the labelled sample | `metrics.sample_estimates.control.in_control` |",
        f"| Failures about wrong, missing or stale challan data | {_pct(s['control']['partial']['share'])} (95% CI {_ci(s['control']['partial']['ci'])}) | `metrics.sample_estimates.control.partial` |",
        f"| Failures described as a physical-court case | {_pct(s['control']['structural']['share'])} (95% CI {_ci(s['control']['structural']['ci'])}) | `metrics.sample_estimates.control.structural` |",
        est("FALSE_SETTLED", 'App showed "Settled" or "Paid" while the government still showed it pending'),
        est("PAID_PENDING", "Paid, still pending on Parivahan or in court"),
        est("REFUND_STUCK", "Refund not received"),
        est("OVERCHARGE", "Charged far above the fine, or fee not shown upfront"),
        est("WRONG_DATA", "Challan shown that does not exist, or missing or stale"),
        f"| Developer replied | {_pct(rep['reply_rate'])} of challan reviews, median {rep['median_reply_hours']:.0f} hours | `metrics.replies` |",
        f"| Replies that point to an email address or a form | {_pct(rep['redirect_share'])} | `metrics.replies.redirect_share` |",
        f"| Replies that give any timeline | {_pct(rep['timeline_share'])} (most common: \"{rep['timelines_quoted'][0][0]}\") | `metrics.replies.timelines_quoted` |",
        "| Settlement or refund timeline in the published terms | none (cars24.com challan page, CarInfo terms, CarInfo refund policy) | `sources:S1`, `sources:S2`, `sources:S3` |",
        f"| Keyword rules on 100 held-out labelled reviews | precision {val['micro_precision']:.2f}, recall {val['micro_recall']:.2f} | `metrics.validation.test` |",
    ]
    if m.get("author_check"):
        a = m["author_check"]
        rows.append(f"| Labels checked blind by the author | {a['vs_sample']['n']} reviews; same labels as the sample on "
                    f"{_pct(a['vs_sample']['exact_match'])}, as the keyword rules on {_pct(a['vs_rules']['exact_match'])} | `metrics.author_check` |")
    return "\n".join(rows)


def update_readme(table: str, check: bool) -> bool:
    path = ROOT / "README.md"
    text = path.read_text()
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    new = f"{head}{START}\n{table}\n{END}{tail}"
    if check:
        return new == text
    path.write_text(new)
    return True


def _jsonable(p: dict) -> dict:
    return {**p, "events": [{**e, "on": e["on"].isoformat()} for e in p["events"]]}


def _replay_json(r: dict) -> dict:
    return {**r, "deadline": r["deadline"].isoformat() if r["deadline"] else None,
            "refund_by": r["refund_by"].isoformat() if r.get("refund_by") else None}


def main(check: bool = False) -> int:
    m = build_metrics()
    table = render_readme_table(m)
    if check:
        ok = update_readme(table, check=True)
        print("README numbers in sync" if ok else "README numbers OUT OF DATE: run python3 build.py")
        return 0 if ok else 1

    mix = {t: m["sample_estimates"]["types"][t]["k"] for t in ("FALSE_SETTLED", "PAID_PENDING", "REFUND_STUCK", "OVERCHARGE")}
    payments = simulate(1000, 24, mix, 0.10, today=TODAY)
    replays = {p["id"]: {"observed": _replay_json(replay(p, TODAY, False)),
                         "truth": _replay_json(replay(p, TODAY, True))} for p in payments}
    (DATA / "metrics.json").write_text(json.dumps(m, indent=2, ensure_ascii=False))
    update_readme(table, check=False)

    bundle = {
        "meta": {"today": TODAY.isoformat(), "simulation": {"n": 1000, "seed": 24, "base_failure_rate": 0.10,
                                                            "mix_from": "hand-labelled sample", "assumed": True}},
        "metrics": m, "sources": json.loads((DATA / "sources.json").read_text()),
        "reviews": [{**r, "types": sorted(classify(r["text"]))} for r in json.loads((DATA / "reviews.json").read_text())],
        "payments": [_jsonable(p) for p in payments], "replays": replays,
    }
    DIST.mkdir(exist_ok=True)
    (DIST / "data.json").write_text(json.dumps(bundle, separators=(",", ":"), ensure_ascii=False))
    page = (ROOT / "web" / "index.html").read_text()
    (DIST / "index.html").write_text(
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n' + page + "\n</html>\n")
    in_ctrl = m["sample_estimates"]["control"]["in_control"]
    print(f"challan reviews {sum(m['challan_reviews'].values())}; in Cars24 control {in_ctrl['share']:.0%} "
          f"(CI {in_ctrl['ci'][0]:.0%}-{in_ctrl['ci'][1]:.0%}); wrote data/metrics.json, README, dist/")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    sys.exit(main(ap.parse_args().check))
