import json
import tempfile
import unittest
from pathlib import Path

from prepare import prepare

SHIPPED = {"id", "app", "at", "score", "ver", "text", "reply", "replied_at"}


def raw(rid, content, at="2026-08-10 10:00:00", score=1, pull="en"):
    return {"reviewId": rid, "at": at, "score": score, "content": content, "replyContent": None,
            "repliedAt": None, "appVersion": "8.2", "userName": "Some Person", "userImage": "http://x",
            "pull": pull, "thumbsUpCount": 0, "reviewCreatedVersion": "8.2"}


class PrepareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.raw_dir, self.out_dir = root / "raw", root / "out"
        self.raw_dir.mkdir()
        rows = [
            raw("a", "paid challan still pending call 9811000001", pull="en"),
            raw("a", "paid challan still pending call 9811000001", pull="hi"),
            raw("b", "app crashes on login"),
            raw("c", "challan paid but pending", score=5),
            raw("d", "challan paid but pending", at="2024-12-31 23:00:00"),
        ]
        for app in ("cars24", "carinfo", "vehicleinfo"):
            (self.raw_dir / f"L_data_{app}.json").write_text(json.dumps({"reviews": rows if app == "carinfo" else []}))
        self.summary = prepare(self.raw_dir, self.out_dir)
        self.reviews = json.loads((self.out_dir / "reviews.json").read_text())
        self.base = json.loads((self.out_dir / "base_counts.json").read_text())

    def tearDown(self):
        self.tmp.cleanup()

    def test_dedupe_by_review_id(self):
        self.assertEqual([r["id"] for r in self.reviews], ["a"])

    def test_shipped_fields_only(self):
        for r in self.reviews:
            self.assertEqual(set(r), SHIPPED)

    def test_text_masked(self):
        self.assertIn("[PHONE]", self.reviews[0]["text"])

    def test_base_counts_low_star_in_window(self):
        # a (deduped) and b are low-star in window; c is 5-star; d is before the window
        self.assertEqual(self.base["low_star"]["carinfo"], {"2026Q3": 2})
        self.assertEqual(len(self.base["raw_sha256"]), 3)


if __name__ == "__main__":
    unittest.main()
