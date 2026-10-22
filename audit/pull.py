"""Optional: re-pull Google Play reviews in the raw format prepare.py reads.

Needs `pip install google-play-scraper`. Output contains reviewer names: keep it out
of the repo (raw/ is gitignored).

Usage:  python3 -m audit.pull --out raw
"""
import argparse
import json
from pathlib import Path

from prepare import APPS


def pull(app_id: str, lang: str, count: int) -> list[dict]:
    from google_play_scraper import Sort, reviews  # imported here so the build never needs it

    out, token = [], None
    while len(out) < count:
        batch, token = reviews(app_id, lang=lang, country="in", sort=Sort.NEWEST, count=200,
                               continuation_token=token)
        out += batch
        if not token or not batch:
            break
    return [{**r, "at": str(r["at"]), "repliedAt": str(r["repliedAt"]) if r.get("repliedAt") else None,
             "pull": lang} for r in out]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="raw")
    ap.add_argument("--count", type=int, default=20000)
    a = ap.parse_args()
    for name, app_id in APPS.items():
        rows = pull(app_id, "en", a.count) + pull(app_id, "hi", a.count // 4)
        Path(a.out, f"L_data_{name}.json").write_text(json.dumps({"app": app_id, "reviews": rows}, default=str))
        print(name, len(rows))
