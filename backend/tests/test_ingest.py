import io

import numpy as np
import pytest
from docx import Document as DocxDocument
from PIL import Image

from app.forensics.ingest import UnsupportedFile, load_document, sniff
from tests.synth import BODY, render, to_bytes, words


def _png_rgba() -> bytes:
    img = Image.new("RGBA", (120, 80), (255, 0, 0, 0))
    img.paste((0, 0, 0, 255), (10, 10, 60, 40))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_sniff_types():
    assert sniff(b"%PDF-1.7 rest") == "pdf"
    assert sniff(_png_rgba()) == "image"
    with pytest.raises(UnsupportedFile):
        sniff(b"PK\x03\x04 not a zip")
    with pytest.raises(UnsupportedFile):
        sniff(b"plain text")


def test_transparent_png_is_flattened_on_white():
    doc, _ = load_document(_png_rgba())
    page = doc.pages[0]
    assert page.image.shape == (80, 120, 3)
    assert tuple(page.image[0, 0]) == (255, 255, 255) and tuple(page.image[20, 20]) == (0, 0, 0)
    assert not page.source_jpeg and doc.metadata["exif"] == "none"


def test_multipage_tiff_and_downscale():
    frames = [Image.new("RGB", (4000, 1000), (i * 40, 0, 0)) for i in range(3)]
    buf = io.BytesIO()
    frames[0].save(buf, "TIFF", save_all=True, append_images=frames[1:])
    doc, _ = load_document(buf.getvalue())
    assert [p.number for p in doc.pages] == [1, 2, 3]
    assert max(doc.pages[0].image.shape[:2]) == 3000


def test_editing_software_in_exif_is_flagged():
    img = Image.new("RGB", (200, 100), (240, 240, 240))
    exif = img.getexif()
    exif[0x0131] = "Adobe Photoshop 25.0"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    doc, _ = load_document(buf.getvalue())
    assert doc.pages[0].source_jpeg
    assert any(f.title == "Saved by image-editing software" for f in doc.findings)


def test_docx_embedded_images_become_pages():
    document = DocxDocument()
    document.add_paragraph("Invoice total 1,200.00")
    document.add_picture(io.BytesIO(to_bytes(render([words(BODY[0], "serif", 30)]))))
    buf = io.BytesIO()
    document.save(buf)
    doc, text = load_document(buf.getvalue())
    assert doc.kind == "docx" and len(doc.pages) == 1
    assert isinstance(doc.pages[0].image, np.ndarray) and "Invoice total" in text
