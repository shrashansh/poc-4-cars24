import unittest
from datetime import date

from engine.settlement import CONFIRM_SOURCES, deadline, replay
from engine.simulate import simulate

D = date.fromisoformat


def pay(kind="online", events=()):
    base = [{"on": D("2026-10-01"), "type": "FEE_SHOWN", "source": "app"},
            {"on": D("2026-10-01"), "type": "PAID", "source": "app"}]
    return {"id": "P1", "app": "carinfo", "kind": kind, "fine": 500, "fee": 100,
            "events": base + [{"on": D(o), "type": t, "source": s} for o, t, s in events]}


class EngineTest(unittest.TestCase):
    def test_deadline_working_days(self):
        self.assertEqual(deadline("online", D("2026-10-16")), D("2026-10-27"))
        self.assertEqual(deadline("refund", D("2026-10-16")), D("2026-10-27"))
        self.assertEqual(deadline("court", D("2026-10-01")), D("2026-12-30"))

    def test_no_settled_without_gov_confirm(self):
        p = pay(events=[("2026-10-03", "PARTNER_PAID", "partner")])
        self.assertEqual(replay(p, D("2026-10-05"), truth_rule=False)["shown_to_user"], "Settled")
        truth = replay(p, D("2026-10-05"), truth_rule=True)
        self.assertNotEqual(truth["shown_to_user"], "Settled")
        self.assertIn("PARTNER_CLAIM_UNCONFIRMED", truth["flags"])

    def test_settled_needs_valid_source(self):
        bad = pay(events=[("2026-10-03", "GOV_CONFIRMED", "partner_said_so")])
        self.assertNotEqual(replay(bad, D("2026-10-05"), True)["status"], "SETTLED")
        good = pay(events=[("2026-10-03", "GOV_CONFIRMED", CONFIRM_SOURCES[0])])
        self.assertEqual(replay(good, D("2026-10-05"), True)["status"], "SETTLED")

    def test_overdue_then_escalated(self):
        p = pay()  # paid 2026-10-01 (Thu); online deadline 2026-10-12
        self.assertEqual(replay(p, D("2026-10-12"), True)["status"], "SUBMITTED")
        overdue = replay(p, D("2026-10-13"), True)
        self.assertEqual((overdue["status"], overdue["owner"]), ("OVERDUE", "partner"))
        esc = replay(p, D("2026-10-15"), True)
        self.assertEqual((esc["status"], esc["owner"]), ("ESCALATED", "ops"))

    def test_escalation_offers_refund(self):
        esc = replay(pay(), D("2026-10-15"), True)  # escalated after 2026-10-14
        self.assertIn("REFUND_OFFERED", esc["flags"])
        self.assertEqual(esc["refund_by"], D("2026-10-26"))

    def test_partner_cannot_confirm(self):
        self.assertNotIn("partner_status_check", CONFIRM_SOURCES)
        self.assertIn("gov_portal_status", CONFIRM_SOURCES)

    def test_deadlines_cite_replies(self):
        from engine.settlement import DEADLINE_SOURCES
        self.assertEqual(set(DEADLINE_SOURCES), {"online", "court", "refund"})
        self.assertTrue(all(v["review_id"] and v["quote"] for v in DEADLINE_SOURCES.values()))

    def test_overdue_message_is_honest(self):
        p = pay()  # due 2026-10-12
        self.assertIn("expected by 2026-10-12", replay(p, D("2026-10-12"), True)["shown_to_user"])
        late = replay(p, D("2026-10-20"), True)["shown_to_user"]
        self.assertNotIn("expected by", late)
        self.assertIn("Overdue since 2026-10-12", late)

    def test_rejected_creates_refund_due(self):
        p = pay(events=[("2026-10-02", "REJECTED", "partner")])
        r = replay(p, D("2026-10-05"), True)
        self.assertEqual((r["status"], r["owner"], r["deadline"]), ("REFUND_DUE", "finance", D("2026-10-13")))
        late = replay(p, D("2026-10-20"), True)
        self.assertIn("REFUND_OVERDUE", late["flags"])
        done = pay(events=[("2026-10-02", "REJECTED", "partner"), ("2026-10-06", "REFUNDED", "bank")])
        self.assertEqual(replay(done, D("2026-10-20"), True)["status"], "REFUNDED")

    def test_fee_shown_before_paid(self):
        p = pay()
        p["events"] = [{"on": D("2026-10-01"), "type": "PAID", "source": "app"}]
        self.assertIn("FEE_NOT_SHOWN", replay(p, D("2026-10-02"), True)["flags"])
        self.assertNotIn("FEE_NOT_SHOWN", replay(pay(), D("2026-10-02"), True)["flags"])

    def test_invariants_all_simulated(self):
        today = D("2026-10-22")
        mix = {"FALSE_SETTLED": 10, "PAID_PENDING": 66, "REFUND_STUCK": 18, "OVERCHARGE": 24}
        payments = simulate(1000, 24, mix, 0.10, today=today)
        self.assertEqual(len(payments), 1000)
        self.assertTrue(all(p["simulated"] for p in payments))
        observed_false = 0
        for p in payments:
            t = replay(p, today, True)
            if t["shown_to_user"] == "Settled":
                self.assertTrue(any(e["type"] == "GOV_CONFIRMED" and e["source"] in CONFIRM_SOURCES
                                    for e in p["events"]))
            if t["status"] not in ("SETTLED", "REFUNDED"):
                self.assertIsNotNone(t["owner"])
                self.assertIsNotNone(t["deadline"])
            o = replay(p, today, False)
            observed_false += o["shown_to_user"] == "Settled" and t["shown_to_user"] != "Settled"
        self.assertGreater(observed_false, 0)

    def test_simulate_is_deterministic(self):
        mix = {"FALSE_SETTLED": 1, "PAID_PENDING": 1, "REFUND_STUCK": 1, "OVERCHARGE": 1}
        self.assertEqual(simulate(50, 24, mix, 0.1), simulate(50, 24, mix, 0.1))


if __name__ == "__main__":
    unittest.main()
