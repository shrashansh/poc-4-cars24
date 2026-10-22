import unittest

from audit.classify import TYPES, classify, control_bucket, is_challan


class ClassifyTest(unittest.TestCase):
    def test_types(self):
        self.assertEqual(TYPES, ("PAID_PENDING", "FALSE_SETTLED", "WRONG_DATA", "REFUND_STUCK",
                                 "OVERCHARGE", "COURT_ROUTING", "OTHER_CHALLAN"))

    def test_paid_pending(self):
        self.assertIn("PAID_PENDING", classify("paid challan 2 months ago still pending on parivahan"))

    def test_false_settled(self):
        self.assertIn("FALSE_SETTLED", classify("app shows settled but parivahan shows pending"))

    def test_wrong_data(self):
        self.assertIn("WRONG_DATA", classify("challan not mine wrong vehicle number"))

    def test_refund_stuck(self):
        self.assertIn("REFUND_STUCK", classify("challan payment failed money deducted no refund yet"))

    def test_overcharge(self):
        self.assertIn("OVERCHARGE", classify("challan fine 500 but charged 1500 extra fees"))

    def test_court_routing(self):
        self.assertIn("COURT_ROUTING",
                      classify("court challan they took money said settled now virtual court notice"))

    def test_hinglish_paid_pending(self):
        self.assertIn("PAID_PENDING", classify("challan ka payment kar diya abhi bhi pending dikha raha"))

    def test_devanagari_challan(self):
        text = "चालान भरा पर अभी भी pending"
        self.assertTrue(is_challan(text))
        self.assertIn("PAID_PENDING", classify(text))

    def test_not_challan(self):
        self.assertFalse(is_challan("app crashes on login"))

    def test_fallback_other(self):
        self.assertEqual(classify("challan feature is good"), {"OTHER_CHALLAN"})

    def test_control_bucket(self):
        self.assertEqual(control_bucket({"FALSE_SETTLED"}, ""), "in_control")
        self.assertEqual(control_bucket({"PAID_PENDING"}, "court challan pending"), "structural")
        self.assertEqual(control_bucket({"WRONG_DATA"}, ""), "partial")
        self.assertEqual(control_bucket({"OTHER_CHALLAN"}, ""), "other")
        self.assertEqual(control_bucket({"COURT_ROUTING", "REFUND_STUCK"}, "court"), "in_control")


if __name__ == "__main__":
    unittest.main()
