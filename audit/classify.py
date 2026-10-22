"""Deterministic keyword rules: is a review about challans, and which failure types does it report.

English, Hinglish and Devanagari. No model, so every build gives the same labels.
"""
import re

TYPES = ("PAID_PENDING", "FALSE_SETTLED", "WRONG_DATA", "REFUND_STUCK",
         "OVERCHARGE", "COURT_ROUTING", "OTHER_CHALLAN")


def _rx(*parts: str) -> re.Pattern:
    return re.compile("|".join(parts), re.I)


CHALLAN = _rx(r"challan", r"chalan", r"chalaan", r"चालान", r"traffic fine", r"fine amount", r"e-?challan")
PAID = _rx(r"\bpaid\b", r"payment", r"\bpay(?:ed|ing)?\b", r"pay ki(?:ya|ye|e)", r"kar diya", r"\bb?h?ara\b",
           r"bhar(?:a|diya|e)\b", r"भर", r"deduct", r"debit", r"\bjama\b", r"took (?:the )?money", r"paise", r"पैसा")
PENDING = _rx(r"pending", r"not (?:been |yet )?(?:cleared|updated|settled|removed|resolved|reflect|paid)",
              r"settle (?:nahi|nahin|nhi)", r"(?:nahi|nahin|nhi) (?:hua|huye|huyae|bara|bhara)", r"clear (?:nahi|nhi)",
              r"na challan pay", r"processing", r"under process", r"in progress", r"फंसा", r"settled yet",
              r"still (?:show|there|pending|unpaid|not|active)", r"abhi bhi", r"अभी भी", r"unpaid",
              r"not clear", r"nahi hua", r"nhi hua", r"same challan", r"still (?:the )?challan")
SETTLED_CLAIM = _rx(r"(?:show|shows|showed|showing|shown) (?:as |the challan as |status as )?[\"'“]?(?:settled|paid|disposed)",
                    r"settle show", r"said (?:it is |challan is |that )?(?:settled|paid)", r"(?:status|marked) (?:is |as )?[\"'“]?(?:settled|paid)",
                    r"cleared in (?:the )?app", r"(?:fake )?clearance message", r"in app it show", r"paid from their side")
WRONG = _rx(r"not mine", r"wrong (?:vehicle|car|number|challan|data|detail|owner|info)", r"incorrect",
            r"(?:fake|false|bogus) challan", r"does ?n[o']?t exist", r"no such challan", r"outdated",
            r"old challan", r"challan (?:is )?not (?:showing|found|visible)", r"not show(?:ing)? (?:my )?challan",
            r"galat", r"already paid.{0,60}(?:show|again)", r"no pending challan", r"not updat", r"misinformation",
            r"inaccurate", r"(?:challan|chalan) not show", r"no challan despite", r"showed no challan")
REFUND = re.compile(r"refund", re.I)
REFUND_NEG = _rx(r"\bno\b", r"\bnot\b", r"\byet\b", r"still", r"pending", r"haven", r"didn", r"nahi", r"nhi",
                 r"waiting", r"never")
FAILED_DEDUCT = _rx(r"fail.{0,60}(?:deduct|debit)", r"(?:deduct|debit).{0,60}(?:fail|unsuccess)", r"money lose",
                    r"unsuccess.{0,60}(?:deduct|debit)")
OVERCHARGE = _rx(r"extra (?:fee|charge|money|amount|rs|₹)", r"additional amount", r"elevated", r"excessive",
                 r"charged (?:me )?(?:rs\.? ?|₹ ?)?\d+ (?:from|for) (?:a )?challan of",
                 r"(?:price|amount) (?:was|is) (?:rs\.? ?|₹ ?)?\d+ but.{0,30}(?:paid|payed|charged)", r"convenience fee", r"charged (?:more|extra|double|twice)",
                 r"(?:double|twice|2x|3x) (?:the )?(?:amount|fine|charge)", r"hidden charge", r"platform fee",
                 r"service (?:fee|charge)", r"more than (?:the )?(?:fine|challan)", r"legal fee",
                 r"fine (?:of |was |is )?(?:rs\.? ?|₹ ?)?\d+.{0,50}charged", r"charged (?:rs\.? ?|₹ ?)?\d+.{0,50}fine")
COURT = _rx(r"court challan", r"cort challan", r"virtual court", r"lok adalat", r"(?:to|in|into) (?:the )?courts?\b",
            r"court (?:handling|fee|charge)", r"न्यायालय", r"कोर्ट")
COURT_MONEY = _rx(r"\bpaid\b", r"payment", r"took (?:the )?money", r"settled", r"charged", r"fee")


def is_challan(text: str) -> bool:
    return bool(CHALLAN.search(text or ""))


def classify(text: str) -> set[str]:
    t = text or ""
    out = set()
    paid, pending = PAID.search(t), PENDING.search(t)
    if paid and pending:
        out.add("PAID_PENDING")
    if SETTLED_CLAIM.search(t) and (pending or re.search(r"parivahan|govt|government|official|rto|unpaid|not (?:actually )?(?:paid|cleared)", t, re.I)):
        out.add("FALSE_SETTLED")
    if WRONG.search(t):
        out.add("WRONG_DATA")
    if (REFUND.search(t) and REFUND_NEG.search(t)) or FAILED_DEDUCT.search(t):
        out.add("REFUND_STUCK")
    if OVERCHARGE.search(t):
        out.add("OVERCHARGE")
    if COURT.search(t) and COURT_MONEY.search(t):
        out.add("COURT_ROUTING")
    return out or {"OTHER_CHALLAN"}


def control_bucket(types: set[str], text: str) -> str:
    court = bool(COURT.search(text or ""))
    if types & {"FALSE_SETTLED", "REFUND_STUCK", "OVERCHARGE"} or ("PAID_PENDING" in types and not court):
        return "in_control"
    if "WRONG_DATA" in types:
        return "partial"
    if types & {"COURT_ROUTING", "PAID_PENDING"}:
        return "structural"
    return "other"
