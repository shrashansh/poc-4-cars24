"""Turn classified challan reviews into the audit numbers.

Every count is a lower bound from self-selected public reviews. Payment volume is
unknown, so no failure rate is computed anywhere.
"""
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime

from audit.classify import TYPES, classify, control_bucket

FAILURE_TYPES = TYPES[:-1]
PARTIAL_QUARTERS = ["2026Q4"]
# Date Cars24 owned each app (sources S10, S11). Earlier reviews describe the previous owner.
ACQUIRED = {"cars24": "2000-01-01", "carinfo": "2026-01-05", "vehicleinfo": "2026-03-11"}
REDIRECT = re.compile(r"\[EMAIL\]|\bform\b|\blink\b|write to us|mail us", re.I)
TIMELINE = re.compile(r"\b\d+\s*(?:-|–|to)?\s*\d*\s*(?:working |business )?days\b", re.I)


def quarter(at: str) -> str:
    return f"{at[:4]}Q{(int(at[5:7]) - 1) // 3 + 1}"


def _hours(a: str, b: str) -> float:
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 3600


def _share(a: float, b: float) -> float:
    return round(a / b, 3) if b else 0.0


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion k/n."""
    if not n:
        return 0.0, 0.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return round(centre - half, 4), round(centre + half, 4)


def sample_estimates(rows: list[dict], population: int) -> dict:
    """Shares from the hand-labelled random sample, independent of the classifier's recall."""
    n = len(rows)

    def est(k: int, base: int) -> dict:
        lo, hi = wilson(k, base)
        return {"k": k, "share": _share(k, base), "ci": [lo, hi],
                "scaled": round(k / base * population) if base else 0,
                "scaled_ci": [round(lo * population), round(hi * population)]}

    types = {t: est(sum(t in r["labels"] for r in rows), n) for t in FAILURE_TYPES}
    failing = [r for r in rows if r["labels"] & set(FAILURE_TYPES)]
    buckets = Counter(control_bucket(r["labels"], r["text"]) for r in failing)
    control = {b: {**est(buckets[b], len(failing)), "scaled": None, "scaled_ci": None}
               for b in ("in_control", "partial", "structural")}
    return {"n": n, "population": population, "failure_reviews": len(failing),
            "not_challan": sum("NOT_CHALLAN" in r["labels"] for r in rows), "types": types, "control": control}


def compute(reviews: list[dict], base_counts: dict, validation: dict, validation_rows: list[dict] | None = None) -> dict:
    labelled = [(r, classify(r["text"])) for r in reviews]
    type_counts = {t: Counter() for t in TYPES}
    by_quarter: dict[str, Counter] = defaultdict(Counter)
    buckets: Counter = Counter()
    for r, types in labelled:
        for t in sorted(types):
            type_counts[t][r["app"]] += 1
            by_quarter[quarter(r["at"])][t] += 1
        buckets[control_bucket(types, r["text"])] += 1

    failing = Counter(quarter(r["at"]) for r, types in labelled if types & set(FAILURE_TYPES))
    test = validation["test"]
    total = len(reviews)
    control = {b: {"count": buckets[b], "share": _share(buckets[b], total)}
               for b in ("in_control", "partial", "structural", "other")}
    low = defaultdict(int)
    for q_counts in base_counts["low_star"].values():
        for q, n in q_counts.items():
            low[q] += n

    estimates = {}
    for t in FAILURE_TYPES:
        obs = sum(type_counts[t].values())
        pt = test["per_type"][t]
        estimates[t] = {"observed": obs, "low": round(obs * pt["precision"]),
                        "high": round(obs * pt["precision"] / pt["recall"]) if pt["recall"] else None,
                        "precision": pt["precision"], "recall": pt["recall"], "support": pt["support"]}

    replied = [r for r in reviews if r.get("reply") and r.get("replied_at")]
    # A reply older than the review means the review was edited after the reply; skip it for latency.
    hours = [h for h in (_hours(r["at"], r["replied_at"]) for r in replied) if h >= 0]
    timelines = Counter(m.group(0).lower() for r in replied for m in TIMELINE.finditer(r["reply"]))

    return {
        "window": base_counts["window"], "pulled_on": base_counts["pulled_on"],
        "raw_sha256": base_counts["raw_sha256"],
        "low_star_total": {a: sum(q.values()) for a, q in base_counts["low_star"].items()},
        "challan_reviews": dict(Counter(r["app"] for r in reviews)),
        "type_counts": {t: dict(c) for t, c in type_counts.items()},
        "by_quarter": {q: dict(sorted(by_quarter[q].items())) for q in sorted(by_quarter)},
        "failing_by_quarter": dict(sorted(failing.items())),
        "partial_quarters": PARTIAL_QUARTERS,
        "q3_vs_q2": {"2026Q2": failing["2026Q2"], "2026Q3": failing["2026Q3"],
                     "ratio": _share(failing["2026Q3"], failing["2026Q2"]),
                     "low_star_q2": low["2026Q2"], "low_star_q3": low["2026Q3"],
                     "share_q2": _share(failing["2026Q2"], low["2026Q2"]),
                     "share_q3": _share(failing["2026Q3"], low["2026Q3"]),
                     "share_ratio": _share(_share(failing["2026Q3"], low["2026Q3"]),
                                           _share(failing["2026Q2"], low["2026Q2"]))},
        "since_acquisition": {
            "dates": {a: d for a, d in ACQUIRED.items() if a != "cars24"},
            "challan_reviews": dict(Counter(r["app"] for r in reviews if r["at"][:10] >= ACQUIRED.get(r["app"], "0"))),
            "failure_reviews": sum(1 for r, types in labelled
                                   if types & set(FAILURE_TYPES) and r["at"][:10] >= ACQUIRED.get(r["app"], "0")),
        },
        "false_settled_total": sum(type_counts["FALSE_SETTLED"].values()),
        "estimates": estimates,
        "control_split": control,
        "replies": {
            "reply_rate": _share(len(replied), total),
            "median_reply_hours": round(statistics.median(hours), 1) if hours else None,
            "redirect_share": _share(sum(bool(REDIRECT.search(r["reply"])) for r in replied), len(replied)),
            "timeline_share": _share(sum(bool(TIMELINE.search(r["reply"])) for r in replied), len(replied)),
            "timelines_quoted": timelines.most_common(10),
        },
        "validation": validation,
        "sample_estimates": sample_estimates(validation_rows, total) if validation_rows else None,
    }
