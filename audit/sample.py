"""Deterministic, app-stratified sample of challan reviews for manual labelling."""
import random


def sample(reviews: list[dict], n: int = 150, seed: int = 24) -> list[dict]:
    by_app: dict[str, list[dict]] = {}
    for r in sorted(reviews, key=lambda r: r["id"]):
        by_app.setdefault(r["app"], []).append(r)
    total = len(reviews)
    quotas = {a: round(n * len(rs) / total) for a, rs in by_app.items()}
    # fix rounding drift on the largest app
    biggest = max(by_app, key=lambda a: len(by_app[a]))
    quotas[biggest] += n - sum(quotas.values())
    rng = random.Random(seed)
    picked = [r for a in sorted(by_app) for r in rng.sample(by_app[a], quotas[a])]
    rng.shuffle(picked)
    return picked
