"""Agreement between the author's blind labels and another labelling (the sample labels or the keyword rules).

Usage:  python3 -m audit.agreement      # prints agreement once data/author_labels.csv exists
"""
import csv
from pathlib import Path

from audit.classify import TYPES

LABELS = TYPES + ("NOT_CHALLAN",)


def _kappa(a: list[bool], b: list[bool]) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


def agreement(author: dict[str, set], other: dict[str, set]) -> dict:
    ids = sorted(set(author) & set(other))
    per_type = {}
    for t in LABELS:
        a = [t in author[i] for i in ids]
        b = [t in other[i] for i in ids]
        per_type[t] = {"agree": sum(x == y for x, y in zip(a, b)), "n": len(ids),
                       "author_count": sum(a), "other_count": sum(b), "kappa": _kappa(a, b)}
    exact = sum(author[i] == other[i] for i in ids)
    return {"n": len(ids), "exact_match": round(exact / len(ids), 3) if ids else 0.0, "per_type": per_type}


def load_author(path: Path) -> dict[str, set]:
    with open(path, newline="") as f:
        return {r["id"]: set(filter(None, r["labels"].split(";"))) for r in csv.DictReader(f)}


if __name__ == "__main__":
    from audit.classify import classify
    from audit.validate import load_rows

    root = Path(__file__).resolve().parent.parent
    author = load_author(root / "data" / "author_labels.csv")
    rows = load_rows(root / "data" / "validation.csv")
    sample = {r["id"]: r["labels"] for r in rows}
    rules = {r["id"]: classify(r["text"]) for r in rows}
    for name, other in (("sample labels", sample), ("keyword rules", rules)):
        r = agreement(author, other)
        print(f"author vs {name}: n={r['n']} exact={r['exact_match']}")
