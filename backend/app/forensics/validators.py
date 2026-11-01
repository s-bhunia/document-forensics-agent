from __future__ import annotations

import re
from datetime import date

from app.forensics.types import Category, Finding, Page, Severity, Word, union_box

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PAN_ENTITY = set("ABCFGHLJPT")

PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
AADHAAR_RE = re.compile(r"\b([2-9]\d{3})\s?(\d{4})\s?(\d{4})\b")
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
DATE_RE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4}|\d{2})\b")


def verhoeff_valid(number: str) -> bool:
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(digit)]]
    return c == 0


def gstin_valid(gstin: str) -> bool:
    total = 0
    for i, ch in enumerate(gstin[:14]):
        value = _GST_CHARS.index(ch) * (2 if i % 2 else 1)
        total += value // 36 + value % 36
    return _GST_CHARS[(36 - total % 36) % 36] == gstin[14]


def pan_valid(pan: str) -> bool:
    return bool(PAN_RE.fullmatch(pan)) and pan[3] in PAN_ENTITY


def date_valid(day: int, month: int, year: int) -> bool:
    if year < 100:
        year += 2000 if year < 50 else 1900
    for d, m in ((day, month), (month, day)):
        try:
            date(year, m, d)
            return True
        except ValueError:
            continue
    return False


def locate(page: Page | None, token: str) -> tuple[int | None, tuple | None]:
    if page is None:
        return None, None
    compact = token.replace(" ", "")
    for line in page.lines().values():
        joined, owners = "", []
        for word in line:
            joined += word.text
            owners += [word] * len(word.text)
        start = joined.find(compact)
        if start >= 0:
            covered: list[Word] = []
            for word in owners[start : start + len(compact)]:
                if word not in covered:
                    covered.append(word)
            return page.number, union_box([w.box for w in covered])
    return page.number, None


def validate_text(text: str, page: Page | None = None) -> list[Finding]:
    findings: list[Finding] = []

    def add(severity, title, detail, token, evidence):
        number, box = locate(page, token)
        findings.append(
            Finding(Category.SEMANTIC, severity, title, detail, page=number, box=box, text=token, evidence=evidence)
        )

    for pan in set(PAN_RE.findall(text)):
        if pan[3] not in PAN_ENTITY:
            add(Severity.MEDIUM, "PAN number has an invalid holder type",
                f"“{pan}”: the 4th character “{pan[3]}” is not a valid PAN holder type.", pan, {"pan": pan})

    for groups in set(AADHAAR_RE.findall(text)):
        number = "".join(groups)
        if not verhoeff_valid(number):
            add(Severity.HIGH, "Aadhaar number fails its checksum",
                f"“{' '.join(groups)}” fails the Verhoeff check digit that every real Aadhaar number passes.",
                " ".join(groups), {"aadhaar": number})

    for gstin in set(GSTIN_RE.findall(text)):
        if not gstin_valid(gstin):
            add(Severity.HIGH, "GSTIN fails its checksum",
                f"“{gstin}”: the last character should be a check digit computed from the first 14.", gstin, {"gstin": gstin})
        elif gstin[5] not in PAN_ENTITY:
            add(Severity.MEDIUM, "GSTIN contains an invalid PAN",
                f"“{gstin}”: the embedded PAN has an invalid holder type.", gstin, {"gstin": gstin})

    for match in DATE_RE.finditer(text):
        day, month, year = (int(g) for g in match.groups())
        if not date_valid(day, month, year):
            add(Severity.MEDIUM, "Impossible date", f"“{match.group(0)}” is not a real calendar date.",
                match.group(0), {"date": match.group(0)})
    return findings


def validate_pages(pages: list[Page], extra_text: str = "") -> list[Finding]:
    findings: list[Finding] = []
    for page in pages:
        text = "\n".join(" ".join(w.text for w in line) for line in page.lines().values())
        findings += validate_text(text, page)
    if extra_text:
        findings += validate_text(extra_text)
    return findings
