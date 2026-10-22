import json
import unittest
from pathlib import Path

from audit.validate import load_rows, score

ROOT = Path(__file__).resolve().parent.parent


class ValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_rows(ROOT / "data" / "validation.csv")

    def test_validation_shape(self):
        self.assertEqual(len(self.rows), 150)
        self.assertEqual(sum(r["split"] == "dev" for r in self.rows), 50)
        self.assertEqual(sum(r["split"] == "test" for r in self.rows), 100)
        ids = {r["id"] for r in json.loads((ROOT / "data" / "reviews.json").read_text())}
        self.assertTrue(all(r["id"] in ids for r in self.rows))

    def test_score_toy(self):
        rows = [{"split": "test", "labels": {"PAID_PENDING"}, "text": "paid challan still pending"},
                {"split": "test", "labels": {"NOT_CHALLAN"}, "text": "challan paid still pending"}]
        s = score(rows, "test")
        self.assertEqual(s["n"], 2)
        self.assertAlmostEqual(s["micro_precision"], 0.5)
        self.assertAlmostEqual(s["micro_recall"], 1.0)

    def test_test_split_precision_floor(self):
        self.assertGreaterEqual(score(self.rows, "test")["micro_precision"], 0.80)


if __name__ == "__main__":
    unittest.main()
