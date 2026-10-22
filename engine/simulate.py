"""SIMULATED challan payments for the engine demo.

The failure mix comes from the hand-labelled review sample. The overall failure rate,
challan kinds, amounts and timings are ASSUMED: Cars24's payment volume is not public.
"""
import random
from datetime import date, timedelta

KIND_SPLIT = {"online": 0.6, "vcourt": 0.25, "court": 0.15}   # ASSUMED
FINES = (250, 500, 1000, 2000, 5000)                            # ASSUMED
FEE_SHARE = 0.25                                                # ASSUMED platform fee as a share of the fine
APPS = ("carinfo", "vehicleinfo", "cars24")


def _ev(on: date, kind: str, source: str) -> dict:
    return {"on": on, "type": kind, "source": source}


def simulate(n: int = 1000, seed: int = 24, mix: dict | None = None, base_failure_rate: float = 0.10,
             start: date = date(2026, 7, 1), today: date = date(2026, 10, 22)) -> list[dict]:
    rng = random.Random(seed)
    mix = mix or {"FALSE_SETTLED": 1, "PAID_PENDING": 1, "REFUND_STUCK": 1, "OVERCHARGE": 1}
    failures, weights = zip(*sorted(mix.items()))
    span = (today - start).days - 1
    out = []
    for i in range(n):
        kind = rng.choices(list(KIND_SPLIT), weights=list(KIND_SPLIT.values()))[0]
        fine = rng.choice(FINES)
        paid_on = start + timedelta(days=rng.randrange(span))
        outcome = rng.choices(failures, weights=weights)[0] if rng.random() < base_failure_rate else "OK"
        events = []
        if outcome != "OVERCHARGE":
            events.append(_ev(paid_on, "FEE_SHOWN", "app"))
        events.append(_ev(paid_on, "PAID", "app"))
        lag = rng.randint(20, 80) if kind == "court" else rng.randint(1, 5)
        if outcome in ("OK", "OVERCHARGE"):
            events += [_ev(paid_on + timedelta(days=lag), "PARTNER_PAID", "partner"),
                       _ev(paid_on + timedelta(days=lag), "GOV_CONFIRMED", "gov_receipt")]
        elif outcome == "FALSE_SETTLED":
            events.append(_ev(paid_on + timedelta(days=2), "PARTNER_PAID", "partner"))
        elif outcome == "REFUND_STUCK":
            events.append(_ev(paid_on + timedelta(days=3), "REJECTED", "partner"))
        events = [e for e in events if e["on"] <= today]
        out.append({"id": f"SIM-{i + 1:04d}", "app": rng.choice(APPS), "kind": kind, "fine": fine,
                    "fee": round(fine * FEE_SHARE), "outcome": outcome, "events": events, "simulated": True})
    return out
