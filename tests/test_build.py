import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PII = {
    "phone": re.compile(r"(?<![\w.-])(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?![\w-])"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "upi": re.compile(r"\b[\w.-]+@(?:ok\w+|ybl|ibl|axl|upi|paytm|apl)\b", re.I),
    "reg": re.compile(r"\b(?:DL|HR|UP|MH|KA|TN|RJ|GJ|WB|MP|PB|TS|AP|KL|BR|CG|OD|JH|UK|HP)[\s-]?\d{1,2}[\s-]?[A-Z]{1,3}[\s-]?\d{4}\b"),
}


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, "build.py"], cwd=ROOT, check=True, capture_output=True)
        cls.dist = json.loads((ROOT / "dist" / "data.json").read_text())

    def test_readme_in_sync(self):
        r = subprocess.run([sys.executable, "build.py", "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_pii_shipped(self):
        files = [ROOT / "dist" / "data.json", *sorted((ROOT / "data").glob("*.json")), ROOT / "data" / "validation.csv"]
        for f in files:
            text = f.read_text()
            self.assertNotIn("userName", text, f.name)
            self.assertNotIn("userImage", text, f.name)
            for name, rx in PII.items():
                hits = [m.group(0) for m in rx.finditer(text) if "cars24.com" not in m.group(0)
                        and not m.group(0).endswith(("cars24.com", ".app", ".gov.in", ".org.in"))]
                self.assertEqual(hits, [], f"{name} in {f.name}: {hits[:3]}")

    def test_no_greeting_names_shipped(self):
        rx = re.compile(r'(?:^|[.!?\n,"]\s*)(?:Hi|Hello|Hey|Dear)\s+(?!\[NAME\]|[Tt]eam\b|[Tt]here\b|[Ss]ir\b|[Mm]adam\b|[Cc]ustomer\b|[Uu]ser\b|[Aa]ll\b)[A-Z][a-z]+', re.M)
        for f in (ROOT / "dist" / "data.json", ROOT / "data" / "reviews.json", ROOT / "data" / "validation.csv"):
            hits = rx.findall(f.read_text())
            self.assertEqual(hits, [], f"{f.name}: {hits[:3]}")

    def test_simulated_flagged(self):
        self.assertTrue(self.dist["payments"])
        self.assertTrue(all(p["simulated"] is True for p in self.dist["payments"]))

    def test_every_number_has_source(self):
        readme = (ROOT / "README.md").read_text()
        block = readme.split("<!-- METRICS:START -->")[1].split("<!-- METRICS:END -->")[0]
        rows = [l for l in block.splitlines() if l.startswith("|") and not l.startswith("|---") and "Source" not in l]
        self.assertGreater(len(rows), 8)
        for row in rows:
            self.assertRegex(row, r"`metrics\.[\w.]+`|`sources:S\d+`", row)

    def test_author_check_row_only_when_present(self):
        sys.path.insert(0, str(ROOT))
        import build
        m = json.loads((ROOT / "data" / "metrics.json").read_text())
        m.pop("author_check", None)
        self.assertNotIn("checked blind by the author", build.render_readme_table(m))
        m["author_check"] = {"vs_sample": {"n": 50, "exact_match": 0.82}, "vs_rules": {"n": 50, "exact_match": 0.7}}
        table = build.render_readme_table(m)
        self.assertIn("checked blind by the author", table)
        self.assertIn("82%", table)

    def test_label_check_page_is_blind(self):
        from audit.label_check import write_page
        import tempfile
        out = write_page(5, Path(tempfile.mkdtemp()) / "lc.html")
        page = out.read_text()
        self.assertNotIn('"labels"', page)
        self.assertIn("author_labels.csv", page)

    def test_reviews_carry_types(self):
        self.assertTrue(all(r["types"] for r in self.dist["reviews"]))

    def test_dist_keys(self):
        self.assertEqual(set(self.dist), {"metrics", "sources", "reviews", "payments", "replays", "meta"})


if __name__ == "__main__":
    unittest.main()
