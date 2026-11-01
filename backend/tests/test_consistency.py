from app.forensics.consistency import analyze_text_consistency
from app.forensics.ocr import extract_words
from app.forensics.textfeatures import measure_page
from app.forensics.types import Category, Page
from tests.synth import BODY, render, scan, words


def _findings(rgb):
    page = Page(number=1, image=rgb, words=extract_words(rgb))
    measure_page(page)
    return page, analyze_text_consistency(page)


def _typography(findings):
    return [f for f in findings if f.category in (Category.TYPOGRAPHY, Category.INK, Category.SHARPNESS)]


def test_clean_document_has_no_text_anomalies():
    rgb = scan(render([words(line, "serif", 34) for line in BODY]))
    page, findings = _findings(rgb)
    assert len(page.words) > 30
    assert _typography(findings) == []


def test_sans_words_inserted_in_serif_line_are_flagged():
    edited = (
        words("The below mentioned student wish to join as", "serif", 34)
        + words("Research Intern in", "sans", 32)
        + words("your organization", "serif", 34)
    )
    rgb = scan(render([words(BODY[0], "serif", 34), edited, words(BODY[2], "serif", 34)]))
    _, findings = _findings(rgb)
    hits = _typography(findings)
    assert hits, "inserted sans-serif words were not flagged"
    flagged = " ".join(f.text or "" for f in hits)
    assert "Research" in flagged or "Intern" in flagged
    assert "University" not in flagged


def test_regular_word_among_bold_values_is_flagged():
    lines = [
        words("NAME DIPAK SHAW KUMAR", "dejavu-bold", 36),
        words("FATHER RABINDRA SHAW SINGH", "dejavu-bold", 36),
        words("NUMBER NXXPS4807N VALID", "dejavu-bold", 36),
        words("BIRTH", "dejavu-bold", 36) + words("04/11/2005", "dejavu", 36) + words("INDIA CARD", "dejavu-bold", 36),
    ]
    _, findings = _findings(scan(render(lines)))
    flagged = [f.text or "" for f in _typography(findings)]
    assert any("2005" in t for t in flagged), flagged
    assert not any("RABINDRA" in t for t in flagged)


DATES = [
    words("Issued 24-01-2007", "sans-bold", 34),
    words("Renewed 09-03-2011", "sans-bold", 34),
    words("Endorsed 15-03-2008", "sans-bold", 34),
    words("Valid 23-01-2027", "sans-bold", 34),
]


def test_matching_dates_pass_width_check():
    _, findings = _findings(scan(render(DATES + [words("Birth 01-12-1985", "sans-bold", 34)])))
    assert not [f for f in findings if f.category == Category.DIGITS]


def test_date_wider_than_matching_dates_is_flagged():
    edited = DATES + [[("Birth", "sans-bold", 34), ("01-12-1985", "sans-bold", 36)]]
    _, findings = _findings(scan(render(edited)))
    digit = [f for f in findings if f.category == Category.DIGITS]
    assert digit and "1985" in (digit[0].text or "")
