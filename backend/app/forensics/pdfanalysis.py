from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import fitz
import numpy as np

from app.forensics.metadata import editing_tool
from app.forensics.types import Category, Document, Finding, Page, Severity, Word

MAX_PAGES = 20
TARGET_SIDE = 2000
_SUBSET = re.compile(r"^[A-Z]{6}\+")
_STYLE = re.compile(r"[-,_]?(bold|italic|oblique|regular|medium|semibold|demibold|light|black|condensed|psmt|mt|ps|bd|it|bi)$")


def _family(font: str) -> str:
    name = _SUBSET.sub("", font).replace(" ", "").lower()
    previous = None
    while previous != name and len(name) > 3:
        previous = name
        name = _STYLE.sub("", name)
    return name


def _pdf_date(value: str | None) -> datetime | None:
    if not value:
        return None
    m = re.match(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?([+\-Z])?(\d{2})?'?(\d{2})?", value)
    if not m:
        return None
    parts = [int(p) if p else d for p, d in zip(m.groups()[:6], (0, 1, 1, 0, 0, 0))]
    try:
        dt = datetime(*parts)
    except ValueError:
        return None
    sign, hh, mm = m.group(7), m.group(8), m.group(9)
    if sign in ("+", "-") and hh:
        offset = timedelta(hours=int(hh), minutes=int(mm or 0))
        return dt.replace(tzinfo=timezone(offset if sign == "+" else -offset))
    return dt.replace(tzinfo=timezone.utc)


def _revisions(raw: bytes) -> int:
    count = raw.count(b"%%EOF")
    if b"/Linearized" in raw[:2048]:
        count -= 1
    return max(count, 1)


def _render(page: fitz.Page) -> tuple[np.ndarray, float]:
    longest = max(page.rect.width, page.rect.height)
    zoom = min(TARGET_SIDE / longest, 4.0)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False, colorspace=fitz.csRGB)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).copy()
    return img, zoom


def _scaled(rect, zoom: float) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = (float(v) * zoom for v in rect)
    return int(x0), int(y0), max(int(x1 - x0), 1), max(int(y1 - y0), 1)


def _image_coverage(page: fitz.Page) -> tuple[float, list[fitz.Rect]]:
    rects = []
    for info in page.get_image_info():
        rect = fitz.Rect(info["bbox"]) & page.rect
        if not rect.is_empty:
            rects.append(rect)
    area = page.rect.width * page.rect.height
    return (max((r.width * r.height for r in rects), default=0.0) / area if area else 0.0), rects


def _font_findings(page: fitz.Page, number: int, zoom: float) -> list[Finding]:
    findings = []
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if sum(c.isalnum() for c in s["text"]) >= 2]
            if len(spans) < 2:
                continue
            weights = Counter()
            for s in spans:
                weights[_family(s["font"])] += len(s["text"].strip())
            sizes = Counter()
            for s in spans:
                sizes[round(s["size"] * 2) / 2] += len(s["text"].strip())
            main_family = weights.most_common(1)[0][0]
            main_size = sizes.most_common(1)[0][0]
            line_text = "".join(s["text"] for s in line["spans"]).strip()
            for s in spans:
                family_diff = _family(s["font"]) != main_family
                size_diff = abs(s["size"] - main_size) > 0.6
                if not (family_diff or size_diff):
                    continue
                reason = (
                    f"font “{_SUBSET.sub('', s['font'])}” instead of the line's “{main_family}”"
                    if family_diff
                    else f"size {s['size']:.1f} pt instead of {main_size:.1f} pt"
                )
                findings.append(
                    Finding(
                        category=Category.TYPOGRAPHY,
                        severity=Severity.HIGH if family_diff else Severity.MEDIUM,
                        title="Font changes within a line",
                        detail=f"“{s['text'].strip()}” uses {reason} in “{line_text[:120]}”.",
                        page=number,
                        box=_scaled(s["bbox"], zoom),
                        text=s["text"].strip(),
                        evidence={"font": s["font"], "size_pt": s["size"], "line_font": main_family, "line_size_pt": main_size},
                    )
                )
    return findings[:20]


def _overlay_findings(page: fitz.Page, number: int, zoom: float, images: list[fitz.Rect]) -> list[Finding]:
    findings = []
    area = page.rect.width * page.rect.height
    for drawing in page.get_drawings():
        fill = drawing.get("fill")
        rect = fitz.Rect(drawing.get("rect"))
        if fill is None or rect.is_empty or not (0.0003 * area < rect.width * rect.height < 0.2 * area):
            continue
        if not any(rect.intersects(img) for img in images):
            continue
        findings.append(
            Finding(
                category=Category.STRUCTURE,
                severity=Severity.MEDIUM,
                title="Filled box drawn over an image",
                detail="A solid rectangle is drawn on top of the page image. This is how content on a scan is "
                "usually hidden or blanked before new text is placed.",
                page=number,
                box=_scaled(rect, zoom),
                evidence={"fill": ",".join(f"{c:.2f}" for c in fill)},
            )
        )
    return findings[:10]


def _typed_over_scan(page: fitz.Page, number: int, zoom: float, coverage: float) -> list[Finding]:
    if coverage < 0.7:
        return []
    try:
        traces = page.get_texttrace()
    except Exception:
        return []
    visible = [t for t in traces if t.get("type") != 3 and t.get("opacity", 1) > 0 and len(t.get("chars", ())) >= 2]
    findings = []
    for t in visible[:10]:
        text = "".join(chr(c[0]) for c in t["chars"]).strip()
        if sum(ch.isalnum() for ch in text) < 2:
            continue
        findings.append(
            Finding(
                category=Category.STRUCTURE,
                severity=Severity.HIGH,
                title="Visible text typed over a scanned page",
                detail=f"“{text}” is real, visible PDF text placed on top of a scanned image. Genuine scans carry "
                "their text inside the image, or as an invisible OCR layer.",
                page=number,
                box=_scaled(t["bbox"], zoom),
                text=text,
                evidence={"font": t.get("font", "")},
            )
        )
    return findings


def _text_words(page: fitz.Page, zoom: float) -> list[Word]:
    words = []
    for x0, y0, x1, y1, text, block, line, _ in page.get_text("words"):
        if not any(c.isalnum() for c in text):
            continue
        words.append(Word(text=text, box=_scaled((x0, y0, x1, y1), zoom), line_id=f"t{block}-{line}"))
    return words


def load_pdf(raw: bytes) -> Document:
    doc = fitz.open(stream=raw, filetype="pdf")
    meta = {k: str(v) for k, v in (doc.metadata or {}).items() if v}
    findings: list[Finding] = []
    checks = ["PDF structure"]

    revisions = _revisions(raw)
    signed = b"/ByteRange" in raw
    meta["revisions"] = str(revisions)
    if revisions > 1:
        findings.append(
            Finding(
                category=Category.STRUCTURE,
                severity=Severity.LOW if signed else Severity.MEDIUM,
                title="PDF was changed after it was first saved",
                detail=f"The file contains {revisions} saved revisions (incremental updates). "
                + ("A digital signature can explain one revision." if signed else "Each revision can add or replace content."),
                evidence={"revisions": revisions, "signed": str(signed)},
            )
        )

    for key in ("producer", "creator"):
        tool = editing_tool(meta.get(key))
        if tool:
            findings.append(
                Finding(
                    category=Category.METADATA,
                    severity=Severity.MEDIUM,
                    title="Made or saved with PDF-editing software",
                    detail=f"The {key} is “{meta[key]}”, a tool used to edit existing PDFs.",
                    evidence={key: meta[key]},
                )
            )
    created, modified = _pdf_date(meta.get("creationDate")), _pdf_date(meta.get("modDate"))
    if created and modified and (modified - created).total_seconds() > 60:
        findings.append(
            Finding(
                category=Category.METADATA,
                severity=Severity.LOW,
                title="Modified after creation",
                detail=f"Created {created:%d %b %Y %H:%M} and modified {modified:%d %b %Y %H:%M}.",
                evidence={"created": str(created), "modified": str(modified)},
            )
        )

    subsets: dict[str, set[str]] = defaultdict(set)
    pages: list[Page] = []
    for index, fpage in enumerate(doc):
        if index >= MAX_PAGES:
            meta["pages_analyzed"] = str(MAX_PAGES)
            break
        number = index + 1
        for font in fpage.get_fonts(full=True):
            name = font[3]
            if _SUBSET.match(name):
                subsets[name[7:]].add(name[:6])
        image, zoom = _render(fpage)
        coverage, image_rects = _image_coverage(fpage)
        words = _text_words(fpage, zoom)
        native = len(words) >= 10 and coverage < 0.5
        pages.append(Page(number=number, image=image, words=words if native else [], from_text_layer=native))
        findings += _font_findings(fpage, number, zoom)
        findings += _overlay_findings(fpage, number, zoom, image_rects)
        findings += _typed_over_scan(fpage, number, zoom, coverage)

    for name, prefixes in subsets.items():
        if len(prefixes) > 1:
            findings.append(
                Finding(
                    category=Category.STRUCTURE,
                    severity=Severity.MEDIUM,
                    title="Same font embedded more than once",
                    detail=f"“{name}” is embedded as {len(prefixes)} separate subsets. Text added later by another "
                    "tool often brings its own copy of the font.",
                    evidence={"font": name, "subsets": len(prefixes)},
                )
            )
    meta["page_count"] = str(doc.page_count)
    return Document(kind="pdf", pages=pages, metadata=meta, findings=findings, checks=checks + ["PDF fonts", "PDF metadata"])
