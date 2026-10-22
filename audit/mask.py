"""Mask personal identifiers in review text before anything is shipped."""
import re

_STATES = ("AN AP AR AS BR CH CG DD DL DN GA GJ HP HR JH JK KA KL LA LD MH ML MN MP MZ NL OD OR PB PY "
           "RJ SK TN TR TS UK UA UP WB").split()

# Order matters: longer or more specific patterns run first.
_GREETING = re.compile(r"(^|[.!?\n]\s*)(hi|hello|hey|dear)\s+(?!team\b|there\b|sir\b|madam\b|customer\b|user\b|all\b)"
                       r"[A-Za-z][\w.]*(?:\s+(?-i:[A-Z])[\w.]*)?", re.I)

_RULES = [
    ("[UPI]", re.compile(r"\b[\w.-]+@(?:ok\w+|ybl|ibl|axl|upi|paytm|apl|\w*bank|sbi|icici|hdfc|kotak|indus|federal|barodampay|pnb|boi|cnrb|freecharge|jio|airtel)\b", re.I)),
    ("[EMAIL]", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("[CHALLAN_NO]", re.compile(r"\b(?:[A-Z]{2}\d{12,}|\d{14,})\b", re.I)),
    ("[ID]", re.compile(r"\b\d{4}[\s-]\d{4}[\s-]\d{4}\b|\b\d{12,13}\b")),
    ("[REG]", re.compile(
        r"(?:\b|(?<=[a-z]))(?:" + "|".join(_STATES) + r")[\s-]?\d{1,2}[\s-]?[A-Z](?:[\s-]?[A-Z]){0,2}[\s-]?\d{1,4}\b"
        r"|\b\d{2}[\s-]?BH[\s-]?\d{4}[\s-]?[A-Z]{1,2}\b", re.I)),
    ("[PHONE]", re.compile(r"(?<![\d+])(?:\+?91[\s-]?|0)?[6-9]\d{2}[\s-]?\d{2}[\s-]?\d{5}(?!\d)"
                           r"|(?<![\d+])(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"
                           r"|(?<!\d)[6-9]\d{2}[\s-]\d{3}[\s-]\d{4}(?!\d)")),
]


def mask(text: str | None) -> str:
    if not text:
        return ""
    text = _GREETING.sub(lambda m: m.group(1) + m.group(2) + " [NAME]", text)
    for tag, rx in _RULES:
        text = rx.sub(tag, text)
    return text
