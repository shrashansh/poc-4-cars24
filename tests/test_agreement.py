import unittest

from audit.agreement import agreement


class AgreementTest(unittest.TestCase):
    def test_exact_and_per_type(self):
        ref = {"a": {"PAID_PENDING"}, "b": {"WRONG_DATA"}, "c": {"OVERCHARGE", "PAID_PENDING"}, "d": {"OTHER_CHALLAN"}}
        author = {"a": {"PAID_PENDING"}, "b": {"OVERCHARGE"}, "c": {"OVERCHARGE", "PAID_PENDING"}, "d": {"OTHER_CHALLAN"}}
        r = agreement(author, ref)
        self.assertEqual(r["n"], 4)
        self.assertEqual(r["exact_match"], 0.75)
        pp = r["per_type"]["PAID_PENDING"]
        self.assertEqual((pp["agree"], pp["n"]), (4, 4))
        self.assertEqual(r["per_type"]["WRONG_DATA"]["agree"], 3)

    def test_only_common_ids_count(self):
        r = agreement({"a": {"WRONG_DATA"}}, {"a": {"WRONG_DATA"}, "z": {"PAID_PENDING"}})
        self.assertEqual((r["n"], r["exact_match"]), (1, 1.0))

    def test_kappa_perfect_and_chance(self):
        ref = {str(i): ({"PAID_PENDING"} if i % 2 else {"WRONG_DATA"}) for i in range(10)}
        self.assertEqual(agreement(ref, ref)["per_type"]["PAID_PENDING"]["kappa"], 1.0)


if __name__ == "__main__":
    unittest.main()
