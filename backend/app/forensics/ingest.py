from __future__ import annotations

import io
import zipfile

import numpy as np
from PIL import Image, ImageOps, ImageSequence

from app.forensics.docxanalysis import load_docx
from app.forensics.metadata import image_metadata
from app.forensics.pdfanalysis import load_pdf
from app.forensics.types import Document, Page

MAX_SIDE = 3000
MAX_FRAMES = 20
Image.MAX_IMAGE_PIXELS = 120_000_000


class UnsupportedFile(ValueError):
    pass


def sniff(raw: bytes) -> str:
    if raw[:5] == b"%PDF-":
        return "pdf"
    if raw[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                if "word/document.xml" in zf.namelist():
                    return "docx"
        except zipfile.BadZipFile:
            pass
        raise UnsupportedFile("Only DOCX files are supported among ZIP-based formats.")
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img.verify()
        return "image"
    except Exception as exc:
        raise UnsupportedFile("File is not a supported image, PDF or DOCX.") from exc


def _to_rgb(frame: Image.Image) -> np.ndarray:
    frame = ImageOps.exif_transpose(frame)
    if frame.mode in ("RGBA", "LA") or (frame.mode == "P" and "transparency" in frame.info):
        rgba = frame.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, (255, 255, 255))
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        frame = canvas
    else:
        frame = frame.convert("RGB")
    if max(frame.size) > MAX_SIDE:
        frame.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    return np.array(frame)


def image_pages(raw: bytes, start: int = 1) -> tuple[list[Page], dict[str, str], list]:
    img = Image.open(io.BytesIO(raw))
    meta, findings = image_metadata(img)
    lossy = (img.format or "").upper() in ("JPEG", "WEBP", "MPO")
    pages = [
        Page(number=start + i, image=_to_rgb(frame.copy()), source_jpeg=lossy)
        for i, frame in enumerate(ImageSequence.Iterator(img))
        if i < MAX_FRAMES
    ]
    return pages, meta, findings


def load_document(raw: bytes) -> tuple[Document, str]:
    kind = sniff(raw)
    if kind == "pdf":
        return load_pdf(raw), ""
    if kind == "docx":
        document, images, text = load_docx(raw)
        for name, data in images:
            try:
                pages, _, findings = image_pages(data, start=len(document.pages) + 1)
            except Exception:
                continue
            document.pages += pages
            for finding in findings:
                finding.detail = f"{finding.detail} (embedded image {name.rsplit('/', 1)[-1]})"
            document.findings += findings
        return document, text
    pages, meta, findings = image_pages(raw)
    return Document(kind="image", pages=pages, metadata=meta, findings=findings, checks=["Image metadata"]), ""
