import json
import unittest

from audit.metrics import compute

BASE = {"window": ["2025-01-01", "2026-10-22"], "pulled_on": "2026-10-22", "raw_sha256": {"carinfo": "x"},
        "low_star": {"carinfo": {"2026Q2": 10, "2026Q3": 20, "2026Q4": 5}}}
SCORE = {"n": 1, "micro_precision": 0.8, "micro_recall": 0.5,
         "per_type": {t: {"precision": 1.0, "recall": 0.5, "support": 1} for t in
                      ("PAID_PENDING", "FALSE_SETTLED", "WRONG_DATA", "REFUND_STUCK", "OVERCHARGE", "COURT_ROUTING")}}


def rv(i, at, text, reply=None, replied_at=None):
    return {"id": str(i), "app": "carinfo", "at": at, "score": 1, "ver": "8.2", "text": text,
            "reply": reply or "", "replied_at": replied_at}


REVIEWS = [
    rv(1, "2026-05-01 10:00:00", "paid challan still pending", "Write to us at [EMAIL]", "2026-05-01 20:00:00"),
    rv(2, "2026-07-01 10:00:00", "app shows settled but parivahan shows pending",
       "Online challans settle in 5-7 working days", "2026-07-02 10:00:00"),
    rv(3, "2026-07-02 10:00:00", "challan not mine wrong vehicle number", "Please fill this form", "2026-07-02 12:00:00"),
    rv(4, "2026-08-01 10:00:00", "challan payment failed money deducted no refund yet", "Sorry", "2026-08-01 11:00:00"),
    rv(5, "2026-09-01 10:00:00", "court challan paid still pending", "Court challans take up to 90 days",
       "2026-09-01 14:00:00"),
    rv(6, "2026-10-05 10:00:00", "challan feature is good"),
]


class MetricsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = compute(REVIEWS, BASE, {"dev": SCORE, "test": SCORE})

    def test_type_counts(self):
        tc = self.m["type_counts"]
        self.assertEqual(tc["PAID_PENDING"]["carinfo"], 2)
        self.assertEqual(tc["FALSE_SETTLED"]["carinfo"], 1)
        self.assertEqual(tc["WRONG_DATA"]["carinfo"], 1)
        self.assertEqual(tc["REFUND_STUCK"]["carinfo"], 1)
        self.assertEqual(self.m["challan_reviews"], {"carinfo": 6})
        self.assertEqual(self.m["false_settled_total"], 1)

    def test_estimates_bound_counts(self):
        e = self.m["estimates"]["PAID_PENDING"]
        self.assertEqual((e["observed"], e["low"], e["high"]), (2, 2, 4))

    def test_reply_metrics_handles_missing(self):
        r = self.m["replies"]
        self.assertAlmostEqual(r["reply_rate"], round(5 / 6, 3))
        self.assertEqual(r["median_reply_hours"], 4.0)
        self.assertAlmostEqual(r["redirect_share"], 0.4)
        self.assertAlmostEqual(r["timeline_share"], 0.4)

    def test_iso_dates_and_reply_before_edit(self):
        reviews = [rv(1, "2026-05-01T10:00:00", "paid challan still pending", "x", "2026-05-01T12:00:00"),
                   rv(2, "2026-05-02 10:00:00", "paid challan still pending", "y", "2021-03-19T12:05:56")]
        r = compute(reviews, BASE, {"dev": SCORE, "test": SCORE})["replies"]
        self.assertEqual(r["reply_rate"], 1.0)
        self.assertEqual(r["median_reply_hours"], 2.0)  # reply older than the (edited) review is excluded

    def test_wilson_interval(self):
        from audit.metrics import wilson
        lo, hi = wilson(10, 150)
        self.assertAlmostEqual(lo, 0.0367, places=3)
        self.assertAlmostEqual(hi, 0.1182, places=3)

    def test_sample_estimates_from_hand_labels(self):
        rows = [{"labels": {"FALSE_SETTLED", "PAID_PENDING"}, "text": ""}] * 10 + \
               [{"labels": {"WRONG_DATA"}, "text": ""}] * 30 + [{"labels": {"OTHER_CHALLAN"}, "text": ""}] * 60
        s = compute(REVIEWS, BASE, {"dev": SCORE, "test": SCORE}, rows)["sample_estimates"]
        self.assertEqual(s["n"], 100)
        fs = s["types"]["FALSE_SETTLED"]
        self.assertEqual(fs["k"], 10)
        self.assertEqual(fs["share"], 0.1)
        self.assertEqual(fs["scaled"], round(0.1 * 6))  # scaled to the 6 challan reviews in the fixture
        self.assertEqual(s["control"]["in_control"]["k"], 10)
        self.assertEqual(s["control"]["partial"]["k"], 30)
        self.assertEqual(s["failure_reviews"], 40)

    def test_q4_marked_partial(self):
        self.assertIn("2026Q4", self.m["partial_quarters"])
        self.assertEqual(set(self.m["q3_vs_q2"]), {"2026Q2", "2026Q3", "ratio", "low_star_q2", "low_star_q3",
                                                    "share_q2", "share_q3", "share_ratio"})
        self.assertEqual((self.m["q3_vs_q2"]["share_q2"], self.m["q3_vs_q2"]["share_q3"]), (0.1, 0.2))
        self.assertEqual(self.m["q3_vs_q2"]["share_ratio"], 2.0)
        self.assertEqual(self.m["q3_vs_q2"]["2026Q2"], 1)
        self.assertEqual(self.m["q3_vs_q2"]["2026Q3"], 4)

    def test_control_shares_sum_to_one(self):
        self.assertAlmostEqual(sum(b["share"] for b in self.m["control_split"].values()), 1.0, places=2)
        self.assertTrue(all(set(b) == {"count", "share"} for b in self.m["control_split"].values()))
        self.assertEqual(self.m["control_split"]["in_control"]["count"], 3)

    def test_no_overall_rate_key(self):
        self.assertNotIn("failure_rate", json.dumps(self.m))


class SinceAcquisitionTest(unittest.TestCase):
    def test_counts_only_reviews_after_cars24_owned_the_app(self):
        reviews = [rv(1, "2025-12-31 10:00:00", "paid challan still pending"),
                   rv(2, "2026-01-05 09:00:00", "paid challan still pending")]
        m = compute(reviews, BASE, {"dev": SCORE, "test": SCORE})
        self.assertEqual(m["since_acquisition"]["challan_reviews"], {"carinfo": 1})
        self.assertEqual(m["since_acquisition"]["dates"]["carinfo"], "2026-01-05")
        self.assertEqual(m["since_acquisition"]["failure_reviews"], 1)


if __name__ == "__main__":
    unittest.main()
