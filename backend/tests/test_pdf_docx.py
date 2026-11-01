import io
import re
import zipfile

import fitz
from docx import Document as DocxDocument
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.forensics.docxanalysis import load_docx
from app.forensics.pdfanalysis import _family, _pdf_date, load_pdf
from app.forensics.types import Category
from tests.synth import BODY, render, scan, to_bytes, words


def _pdf(lines: list[list[tuple[str, str]]], producer: str | None = None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    if producer:
        c.setProducer(producer)
    y = 780
    for line in lines:
        text = c.beginText(60, y)
        for chunk, fontname in line:
            text.setFont(fontname, 12)
            text.textOut(chunk + " ")
        c.drawText(text)
        y -= 22
    c.save()
    return buf.getvalue()


CLEAN = [[(line, "Times-Roman")] for line in BODY * 3]


def test_family_normalization():
    assert _family("ABCDEF+TimesNewRomanPS-BoldMT") == _family("TimesNewRomanPSMT")
    assert _family("Arial-BoldMT") == _family("ArialMT")
    assert _family("Helvetica") != _family("Times-Roman")


def test_pdf_date_parsing():
    assert _pdf_date("D:20260727222318+05'30'").utcoffset().total_seconds() == 19800
    assert _pdf_date("garbage") is None


def test_clean_pdf_has_no_font_findings():
    doc = load_pdf(_pdf(CLEAN))
    assert doc.kind == "pdf" and len(doc.pages) == 1
    assert doc.pages[0].from_text_layer and len(doc.pages[0].words) > 20
    assert not [f for f in doc.findings if f.category == Category.TYPOGRAPHY]


def test_font_switch_inside_line_is_flagged():
    lines = CLEAN[:3] + [[("wish to join as", "Times-Roman"), ("Research Intern", "Helvetica"), ("in your organization", "Times-Roman")]]
    doc = load_pdf(_pdf(lines))
    hits = [f for f in doc.findings if f.category == Category.TYPOGRAPHY]
    assert len(hits) == 1 and "Research Intern" in hits[0].text
    assert hits[0].box is not None and hits[0].page == 1


def test_editing_producer_and_incremental_update(tmp_path):
    path = tmp_path / "doc.pdf"
    path.write_bytes(_pdf(CLEAN, producer="iLovePDF"))
    with fitz.open(path) as pdf:
        pdf[0].insert_text((60, 500), "Amount: 99,000", fontsize=12)
        pdf.saveIncr()
    doc = load_pdf(path.read_bytes())
    titles = {f.title for f in doc.findings}
    assert "PDF was changed after it was first saved" in titles
    assert "Made or saved with PDF-editing software" in titles
    assert int(doc.metadata["revisions"]) == 2


def test_scanned_pdf_with_whiteout_and_typed_text():
    scan_png = to_bytes(scan(render([words(l, "serif", 34) for l in BODY])))
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=scan_png, keep_proportion=False)
    page.draw_rect(fitz.Rect(100, 200, 260, 230), color=(1, 1, 1), fill=(1, 1, 1))
    page.insert_text((105, 222), "Rs. 79,574", fontsize=14)
    doc = load_pdf(pdf.tobytes())
    titles = {f.title for f in doc.findings}
    assert "Filled box drawn over an image" in titles
    assert "Visible text typed over a scanned page" in titles
    assert not doc.pages[0].from_text_layer


def _docx(paragraphs: list[list[tuple[str, str | None]]]) -> bytes:
    document = DocxDocument()
    for runs in paragraphs:
        p = document.add_paragraph()
        for text, fontname in runs:
            run = p.add_run(text)
            run.font.size = Pt(11)
            if fontname:
                run.font.name = fontname
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def test_docx_font_change_is_flagged():
    raw = _docx([[("The total amount payable is ", "Calibri"), ("79,574.00", "Arial"), (" only, as agreed.", "Calibri")]])
    doc, images, text = load_docx(raw)
    hits = [f for f in doc.findings if f.category == Category.TYPOGRAPHY]
    assert hits and hits[0].text == "79,574.00"
    assert "79,574.00" in text and images == []


def test_docx_clean_and_tracked_changes():
    raw = _docx([[("A normal paragraph of text.", "Calibri")], [("Another one.", "Calibri")]])
    doc, _, _ = load_docx(raw)
    assert not [f for f in doc.findings if f.category == Category.TYPOGRAPHY]

    src = zipfile.ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/document.xml":
                data = re.sub(
                    rb"(<w:r>)",
                    rb'<w:ins w:id="1" w:author="x" w:date="2026-01-01T00:00:00Z">\1',
                    data,
                    count=1,
                ).replace(b"</w:r>", b"</w:r></w:ins>", 1)
            dst.writestr(item, data)
    doc, _, _ = load_docx(out.getvalue())
    assert any(f.title == "Tracked changes present" for f in doc.findings)
