from app.forensics.validators import (
    _GST_CHARS,
    _VERHOEFF_D,
    _VERHOEFF_P,
    date_valid,
    gstin_valid,
    pan_valid,
    validate_text,
    verhoeff_valid,
)

_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def _verhoeff_digit(number: str) -> str:
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(digit)]]
    return str(_INV[c])


def _gstin(body: str) -> str:
    total = 0
    for i, ch in enumerate(body):
        value = _GST_CHARS.index(ch) * (2 if i % 2 else 1)
        total += value // 36 + value % 36
    return body + _GST_CHARS[(36 - total % 36) % 36]


VALID_AADHAAR = "23412341234" + _verhoeff_digit("23412341234")
VALID_GSTIN = _gstin("27AAPFU0939F1Z")


def test_verhoeff():
    assert verhoeff_valid(VALID_AADHAAR)
    bad = VALID_AADHAAR[:-1] + str((int(VALID_AADHAAR[-1]) + 1) % 10)
    assert not verhoeff_valid(bad)


def test_gstin_checksum():
    assert gstin_valid(VALID_GSTIN)
    wrong = VALID_GSTIN[:-1] + ("A" if VALID_GSTIN[-1] != "A" else "B")
    assert not gstin_valid(wrong)


def test_pan_and_dates():
    assert pan_valid("NXXPS4807N")
    assert not pan_valid("NXXQS4807N")
    assert date_valid(31, 12, 2020) and date_valid(12, 31, 2020)
    assert not date_valid(31, 2, 2020) and not date_valid(45, 13, 2020)


def test_validate_text_flags_only_bad_values():
    good = f"PAN NXXPS4807N Aadhaar {VALID_AADHAAR[:4]} {VALID_AADHAAR[4:8]} {VALID_AADHAAR[8:]} GSTIN {VALID_GSTIN} on 24/01/2007"
    assert validate_text(good) == []

    bad_aadhaar = VALID_AADHAAR[:-1] + str((int(VALID_AADHAAR[-1]) + 3) % 10)
    bad_gstin = VALID_GSTIN[:-1] + ("0" if VALID_GSTIN[-1] != "0" else "1")
    bad = f"PAN NXXQS4807N Aadhaar {bad_aadhaar} GSTIN {bad_gstin} dated 31/02/2021"
    titles = {f.title for f in validate_text(bad)}
    assert titles == {
        "PAN number has an invalid holder type",
        "Aadhaar number fails its checksum",
        "GSTIN fails its checksum",
        "Impossible date",
    }
