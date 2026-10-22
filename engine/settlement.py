"""Challan settlement state machine.

Truth rule: the user is shown "Settled" only after a government confirmation that
has a named source. Every open payment has an owner and a deadline; a rejected
payment becomes a refund that is due by a date.

Deadlines come from Cars24's own replies on Play (online 5-7 working days, court up
to 90 days, refunds 5-7 working days; see DEADLINE_SOURCES). Working days are Mon-Fri, no holidays (ASSUMED).
"""
from datetime import date, timedelta

STATES = ("INITIATED", "FEE_SHOWN", "PAID", "ROUTED", "SUBMITTED", "GOV_CONFIRMED", "SETTLED",
          "OVERDUE", "ESCALATED", "REJECTED", "REFUND_DUE", "REFUNDED")
# A partner's word is never a confirmation: only the government receipt or a status read from the government portal.
CONFIRM_SOURCES = ("gov_receipt", "gov_portal_status", "manual_portal_check")
# Each deadline is the timeline Cars24 support itself quotes in Play replies (review IDs from data/reviews.json).
DEADLINE_SOURCES = {
    "online": {"review_id": "5496c0ef-a7e6-4565-8d44-91c0d14c09ba", "replied": "2026-02-09",
               "quote": "Our standard timeline to settle a online challan is 5–7 working days"},
    "court": {"review_id": "194cd4ca-792e-475d-80db-eaf82048a5f1", "replied": "2026-10-22",
              "quote": "Court challan settlements may take up to 90 days"},
    "refund": {"review_id": "16a085f3-52cf-45ff-b8c0-3cb3207e9dd2", "replied": "2025-05-21",
               "quote": "We have already initiated the refund for your challan, and it typically takes 5–7 working days"},
}
WORKING_DAYS = {"online": 7, "vcourt": 7, "refund": 7}   # vcourt: ASSUMED, payable online per e-challan site
CALENDAR_DAYS = {"court": 90}
ESCALATE_AFTER = 2  # working days past the deadline


def add_working_days(start: date, n: int) -> date:
    d = start
    while n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def deadline(kind: str, start: date) -> date:
    if kind in CALENDAR_DAYS:
        return start + timedelta(days=CALENDAR_DAYS[kind])
    return add_working_days(start, WORKING_DAYS[kind])


def _first(events: list[dict], kind: str, today: date, sources=None):
    for e in events:
        if e["type"] == kind and e["on"] <= today and (sources is None or e["source"] in sources):
            return e
    return None


def replay(payment: dict, today: date, truth_rule: bool) -> dict:
    ev = sorted(payment["events"], key=lambda e: e["on"])
    paid = _first(ev, "PAID", today)
    rejected = _first(ev, "REJECTED", today)
    refunded = _first(ev, "REFUNDED", today)
    partner = _first(ev, "PARTNER_PAID", today)
    confirmed = _first(ev, "GOV_CONFIRMED", today, CONFIRM_SOURCES if truth_rule else None)
    out = {"status": "INITIATED", "owner": None, "deadline": None, "refund_by": None, "shown_to_user": "Not paid", "flags": []}
    if not paid:
        return out

    if not truth_rule:  # what the app shows today, per review patterns
        if rejected:
            out.update(status="REJECTED", shown_to_user="Payment rejected")
        elif confirmed or partner:
            out.update(status="SETTLED", shown_to_user="Settled")
        else:
            out.update(status="SUBMITTED", shown_to_user="Processing")
        return out

    fee = _first(ev, "FEE_SHOWN", today)
    if not fee or fee["on"] > paid["on"] or ev.index(fee) > ev.index(paid):
        out["flags"].append("FEE_NOT_SHOWN")
    if partner and not confirmed:
        out["flags"].append("PARTNER_CLAIM_UNCONFIRMED")

    if rejected:
        if refunded:
            out.update(status="REFUNDED", shown_to_user="Refunded")
        else:
            due = deadline("refund", rejected["on"])
            out.update(status="REFUND_DUE", owner="finance", deadline=due,
                       shown_to_user=f"Refund due by {due.isoformat()}")
            if today > due:
                out["flags"].append("REFUND_OVERDUE")
    elif confirmed:
        out.update(status="SETTLED", shown_to_user="Settled")
    else:
        due = deadline(payment["kind"], paid["on"])
        # Overdue for ESCALATE_AFTER full working days, then escalate on the next working day
        # (never on a weekend).
        escalate_from = add_working_days(due, ESCALATE_AFTER + 1)
        if today >= escalate_from:
            status, owner = "ESCALATED", "ops"
            out["refund_by"] = deadline("refund", escalate_from)   # user may take a refund instead of waiting
            out["flags"].append("REFUND_OFFERED")
        elif today > due:
            status, owner = "OVERDUE", "partner"
        else:
            status, owner = "SUBMITTED", "partner"
        shown = (f"Processing, expected by {due.isoformat()}" if status == "SUBMITTED"
                 else f"Overdue since {due.isoformat()}; " + (f"escalated; you can take a refund by {out['refund_by'].isoformat()}" if status == "ESCALATED"
                                                             else "being chased with our partner"))
        out.update(status=status, owner=owner, deadline=due, shown_to_user=shown)
    return out
