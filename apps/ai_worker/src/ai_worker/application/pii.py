from __future__ import annotations

import re

_PII_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("dni", re.compile(r"\b[0-9]{8}[A-Z]\b", re.I), "[REDACTED_DNI]"),
    ("nie", re.compile(r"\b[XYZ][0-9]{7}[A-Z]\b", re.I), "[REDACTED_NIE]"),
    ("iban", re.compile(r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}\b", re.I), "[REDACTED_IBAN]"),
    ("cups", re.compile(r"\bES[0-9]{16}[A-Z]{2}\b", re.I), "[REDACTED_CUPS]"),
    (
        "phone",
        re.compile(r"\b(?:\+34|0034)?[\s.-]?[6789]\d{2}[\s.-]?\d{3}[\s.-]?\d{3}\b"),
        "[REDACTED_PHONE]",
    ),
    (
        "email",
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
        "[REDACTED_EMAIL]",
    ),
]


def redact_pii(text: str) -> str:
    out = text
    for _name, regex, placeholder in _PII_PATTERNS:
        out = regex.sub(placeholder, out)
    return out
