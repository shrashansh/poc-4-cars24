import re
import unittest
from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "web" / "index.html").read_text()


class WebTest(unittest.TestCase):
    def test_tabs_present(self):
        for tab in ("audit", "evidence", "engine", "inspection", "method"):
            self.assertRegex(PAGE, rf'id="{tab}"')

    def test_simulated_label(self):
        engine = PAGE.split('id="engine"')[1].split('id="inspection"')[0]
        self.assertIn("SIMULATED", engine)

    def test_no_rate_claim_label(self):
        audit = PAGE.split('id="audit"')[1].split('id="evidence"')[0]
        self.assertIn("no failure <i>rate</i> is shown", audit)

    def test_no_external_scripts(self):
        for src in re.findall(r'<script[^>]+src="([^"]+)"', PAGE):
            self.assertRegex(src, r"^https://(cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net|unpkg\.com)/")

    def test_dark_mode_and_tokens(self):
        self.assertIn(":root", PAGE)
        self.assertIn("prefers-color-scheme: dark", PAGE)

    def test_reads_data_json(self):
        self.assertIn("data.json", PAGE)


if __name__ == "__main__":
    unittest.main()
