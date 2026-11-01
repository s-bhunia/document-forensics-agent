from __future__ import annotations

import io
import zipfile
from collections import Counter

from docx import Document as DocxDocument
from docx.oxml.ns import qn

from app.forensics.types import Category, Document, Finding, Severity

W_RSID = qn("w:rsidR")


def _effective_font(run, paragraph) -> tuple[str | None, float | None]:
    name = run.font.name or (paragraph.style.font.name if paragraph.style is not None else None)
    size = run.font.size or (paragraph.style.font.size if paragraph.style is not None else None)
    return name, (size.pt if size is not None else None)


def _paragraph_findings(doc) -> list[Finding]:
    findings: list[Finding] = []
    for paragraph in doc.paragraphs:
        runs = [r for r in paragraph.runs if sum(c.isalnum() for c in r.text) >= 2]
        if len(runs) < 2:
            continue
        fonts = Counter()
        sizes = Counter()
        rsids = Counter()
        props = []
        for run in runs:
            name, size = _effective_font(run, paragraph)
            rsid = run._r.get(W_RSID)
            props.append((run, name, size, rsid))
            fonts[name] += len(run.text)
            sizes[size] += len(run.text)
            rsids[rsid] += len(run.text)
        main_font = fonts.most_common(1)[0][0]
        main_size = sizes.most_common(1)[0][0]
        main_rsid = rsids.most_common(1)[0][0]
        for run, name, size, rsid in props:
            text = run.text.strip()
            if name != main_font and name and main_font:
                findings.append(
                    Finding(
                        category=Category.TYPOGRAPHY,
                        severity=Severity.MEDIUM,
                        title="Font changes inside a paragraph",
                        detail=f"“{text}” is set in {name} while the rest of the paragraph uses {main_font}.",
                        text=text,
                        evidence={"font": name, "paragraph_font": main_font},
                    )
                )
            elif size and main_size and abs(size - main_size) >= 1:
                findings.append(
                    Finding(
                        category=Category.TYPOGRAPHY,
                        severity=Severity.LOW,
                        title="Text size changes inside a paragraph",
                        detail=f"“{text}” is {size:g} pt while the rest of the paragraph is {main_size:g} pt.",
                        text=text,
                        evidence={"size_pt": size, "paragraph_size_pt": main_size},
                    )
                )
            if rsid and main_rsid and rsid != main_rsid and any(c.isdigit() for c in text) and len(rsids) > 1:
                findings.append(
                    Finding(
                        category=Category.STRUCTURE,
                        severity=Severity.LOW,
                        title="Value typed in a later editing session",
                        detail=f"“{text}” carries a different Word editing-session ID than the text around it, so it "
                        "was typed or pasted at a different time.",
                        text=text,
                        evidence={"session": rsid, "paragraph_session": main_rsid},
                    )
                )
    return findings[:25]


def load_docx(raw: bytes) -> tuple[Document, list[tuple[str, bytes]], str]:
    doc = DocxDocument(io.BytesIO(raw))
    core = doc.core_properties
    meta = {
        "author": core.author or "",
        "last_modified_by": core.last_modified_by or "",
        "revision": str(core.revision or ""),
        "created": core.created.isoformat() if core.created else "",
        "modified": core.modified.isoformat() if core.modified else "",
    }
    meta = {k: v for k, v in meta.items() if v}
    findings = _paragraph_findings(doc)

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        body = zf.read("word/document.xml")
        insertions, deletions = body.count(b"<w:ins "), body.count(b"<w:del ")
        images = [(n, zf.read(n)) for n in zf.namelist() if n.startswith("word/media/")]
        has_comments = "word/comments.xml" in zf.namelist()
        try:
            app_xml = zf.read("docProps/app.xml").decode("utf-8", "ignore")
            if "<Application>" in app_xml:
                meta["application"] = app_xml.split("<Application>")[1].split("</Application>")[0]
        except KeyError:
            pass

    if insertions or deletions:
        findings.append(
            Finding(
                category=Category.STRUCTURE,
                severity=Severity.MEDIUM,
                title="Tracked changes present",
                detail=f"The document still holds {insertions} tracked insertions and {deletions} deletions.",
                evidence={"insertions": insertions, "deletions": deletions},
            )
        )
    if has_comments:
        meta["comments"] = "yes"
    author, editor = meta.get("author"), meta.get("last_modified_by")
    if author and editor and author != editor:
        findings.append(
            Finding(
                category=Category.METADATA,
                severity=Severity.INFO,
                title="Last edited by a different person",
                detail=f"Created by “{author}”, last saved by “{editor}”.",
                evidence={"author": author, "last_modified_by": editor},
            )
        )
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    for table in doc.tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text.strip() for cell in row.cells)
    document = Document(kind="docx", pages=[], metadata=meta, findings=findings, checks=["DOCX formatting", "DOCX metadata"])
    return document, images, text
