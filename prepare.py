"""Local, one-time step: raw Play review pulls -> masked, challan-only data/ files.

Raw pulls contain reviewer names and photos; they stay in raw/ (gitignored) and
are never copied. Only the fields below, with personal identifiers masked, are shipped.

Usage:  python3 prepare.py [--raw raw] [--out data]
"""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from audit.classify import is_challan
from audit.mask import mask

APPS = {
    "cars24": "com.cars24.seller",
    "carinfo": "com.cuvora.carinfo",
    "vehicleinfo": "com.vehicle.rto.vahan.status.information.register",
}
WINDOW = ("2025-01-01", "2026-10-22")
PULLED_ON = "2026-10-22"


def quarter(at: str) -> str:
    return f"{at[:4]}Q{(int(at[5:7]) - 1) // 3 + 1}"


def prepare(raw_dir: Path, out_dir: Path) -> dict:
    shipped, low_star, sha = [], defaultdict(lambda: defaultdict(int)), {}
    for app in APPS:
        path = Path(raw_dir) / f"L_data_{app}.json"
        blob = path.read_bytes()
        sha[app] = hashlib.sha256(blob).hexdigest()
        data = json.loads(blob)
        rows = data["reviews"] if isinstance(data, dict) else data
        seen = set()
        for r in rows:
            at = str(r["at"])[:19]
            if r["reviewId"] in seen or r["score"] > 2 or not (WINDOW[0] <= at[:10] <= WINDOW[1]):
                continue
            seen.add(r["reviewId"])
            low_star[app][quarter(at)] += 1
            if is_challan(r.get("content") or ""):
                shipped.append({
                    "id": r["reviewId"], "app": app, "at": at, "score": r["score"],
                    "ver": r.get("appVersion"), "text": mask(r.get("content")),
                    "reply": mask(r.get("replyContent")),
                    "replied_at": str(r["repliedAt"])[:19] if r.get("repliedAt") else None,
                })
    shipped.sort(key=lambda r: (r["app"], r["at"], r["id"]))
    base = {"window": list(WINDOW), "pulled_on": PULLED_ON, "apps": APPS, "raw_sha256": sha,
            "low_star": {a: dict(sorted(q.items())) for a, q in low_star.items()}}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "reviews.json").write_text(json.dumps(shipped, ensure_ascii=False, indent=0))
    (out / "base_counts.json").write_text(json.dumps(base, indent=2))
    return {"challan_reviews": len(shipped),
            "low_star": {a: sum(q.values()) for a, q in low_star.items()}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="raw")
    ap.add_argument("--out", default="data")
    a = ap.parse_args()
    print(prepare(Path(a.raw), Path(a.out)))
