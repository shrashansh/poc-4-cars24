"""Score the rules classifier against the hand-labelled validation set.

Precision and recall are computed over the six failure types. OTHER_CHALLAN is the
residual bucket and is not scored; a NOT_CHALLAN row makes every predicted failure
type a false positive.
"""
import csv
import json
from pathlib import Path

from audit.classify import TYPES, classify

FAILURE_TYPES = TYPES[:-1]


def load_rows(csv_path: Path, reviews_path: Path | None = None) -> list[dict]:
    csv_path = Path(csv_path)
    reviews_path = reviews_path or csv_path.parent / "reviews.json"
    text = {r["id"]: r["text"] for r in json.loads(Path(reviews_path).read_text())}
    with open(csv_path, newline="") as f:
        return [{**r, "row": int(r["row"]), "labels": set(r["labels"].split(";")), "text": text[r["id"]]}
                for r in csv.DictReader(f)]


def _ratio(a: int, b: int) -> float:
    return round(a / b, 3) if b else 0.0


def score(rows: list[dict], split: str) -> dict:
    rows = [r for r in rows if r["split"] == split]
    tp = {t: 0 for t in FAILURE_TYPES}
    fp, fn = dict(tp), dict(tp)
    for r in rows:
        pred = classify(r["text"]) & set(FAILURE_TYPES)
        gold = r["labels"] & set(FAILURE_TYPES)
        for t in FAILURE_TYPES:
            tp[t] += t in pred and t in gold
            fp[t] += t in pred and t not in gold
            fn[t] += t in gold and t not in pred
    TP, FP, FN = sum(tp.values()), sum(fp.values()), sum(fn.values())
    return {
        "n": len(rows),
        "micro_precision": _ratio(TP, TP + FP),
        "micro_recall": _ratio(TP, TP + FN),
        "per_type": {t: {"precision": _ratio(tp[t], tp[t] + fp[t]), "recall": _ratio(tp[t], tp[t] + fn[t]),
                         "support": tp[t] + fn[t]} for t in FAILURE_TYPES},
    }
