from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np

from app.forensics import imageforensics as imf
from app.forensics.consistency import analyze_text_consistency
from app.forensics.ingest import load_document
from app.forensics.ocr import extract_words, group_lines
from app.forensics.scoring import label, risk, rule_summary, sort_findings
from app.forensics.textfeatures import measure_page
from app.forensics.types import Category, Document, Finding, Page
from app.forensics.validators import validate_pages

MAX_FINDINGS = 60

CHECKS = {
    "Typography consistency": {Category.TYPOGRAPHY},
    "Ink and sharpness": {Category.INK, Category.SHARPNESS},
    "Digit widths": {Category.DIGITS},
    "Line alignment": {Category.ALIGNMENT},
    "Copy-move detection": {Category.COPY_MOVE},
    "Compression analysis": {Category.COMPRESSION},
    "Background grain": {Category.NOISE},
    "File metadata": {Category.METADATA},
    "File structure": {Category.STRUCTURE},
    "ID number and date checks": {Category.SEMANTIC},
}

FACT_CATEGORIES = {Category.METADATA, Category.STRUCTURE, Category.SEMANTIC}
log = logging.getLogger(__name__)


class Investigates(Protocol):
    def run(self, scan: Any) -> Any: ...


class Timer:
    def __init__(self) -> None:
        self.ms: dict[str, int] = {}

    def run(self, name: str, fn, *args, **kwargs):
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            self.ms[name] = self.ms.get(name, 0) + int((time.perf_counter() - start) * 1000)


def _save(path: Path, rgb: np.ndarray, quality: int = 88) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality])


def _analyze_page(page: Page, lang: str, timer: Timer, out_dir: Path) -> tuple[list[Finding], dict[str, str]]:
    if not page.words:
        page.words = timer.run("ocr", extract_words, page.image, lang)
    timer.run("text_features", measure_page, page)
    findings = timer.run("text_consistency", analyze_text_consistency, page)
    layers: dict[str, str] = {}
    if not page.from_text_layer:
        ela_layer, ela_findings = timer.run("ela", imf.error_level, page)
        noise_layer, noise_findings = timer.run("noise", imf.noise_map, page)
        findings += ela_findings + noise_findings
        findings += timer.run("copy_move", imf.copy_move, page)
        for name, layer in (("ela", ela_layer), ("noise", noise_layer)):
            rel = f"layers/{page.number}_{name}.jpg"
            _save(out_dir / rel, layer, 82)
            layers[name] = rel
    return findings, layers


def _checks(document: Document, findings: list[Finding], ran: set[str]) -> list[str]:
    hit = {f.category for f in findings}
    passed = [name for name, cats in CHECKS.items() if name in ran and not (cats & hit)]
    return passed + [c for c in document.checks if c not in passed]


def _ran_checks(document: Document) -> set[str]:
    ran = {"File metadata", "ID number and date checks"}
    if document.kind == "pdf":
        ran.add("File structure")
    if document.kind == "docx":
        ran |= {"File structure", "Typography consistency"}
    if document.pages:
        ran |= {"Typography consistency", "Ink and sharpness", "Digit widths", "Line alignment"}
    if any(not p.from_text_layer for p in document.pages):
        ran |= {"Copy-move detection", "Compression analysis", "Background grain"}
    return ran


def _merge_facts(agent_findings: list[Finding], leads: list[Finding]) -> list[Finding]:
    seen = {(f.title, f.text) for f in agent_findings}
    facts = [f for f in leads if f.category in FACT_CATEGORIES and (f.title, f.text) not in seen]
    return agent_findings + facts


def analyze_file(raw: bytes, out_dir: Path, lang: str = "eng", investigator: Investigates | None = None) -> dict[str, Any]:
    timer = Timer()
    out_dir.mkdir(parents=True, exist_ok=True)
    document, extra_text = timer.run("load", load_document, raw)
    findings = list(document.findings)
    pages_out = []

    for page in document.pages:
        page_findings, layers = _analyze_page(page, lang, timer, out_dir)
        findings += page_findings
        image_rel = f"pages/{page.number}.jpg"
        _save(out_dir / image_rel, page.image)
        pages_out.append({"number": page.number, "width": page.width, "height": page.height, "image": image_rel, "layers": layers})

    findings += timer.run("cross_page", imf.cross_page_copies, document.pages)
    findings += timer.run("validators", validate_pages, document.pages, extra_text)

    sizes = {p.number: (p.width, p.height) for p in document.pages}
    ocr = [
        {
            "page": p.number,
            "lines": [
                {"text": l["text"], "box": [round(v / d, 4) for v, d in zip(l["box"], (p.width, p.height, p.width, p.height))]}
                for l in group_lines(p.words)
            ],
        }
        for p in document.pages
    ]

    findings = sort_findings(findings)
    summary_source, summary, investigation = "rules", None, None
    if investigator is not None:
        from app.agent.workspace import Scan

        try:
            report = timer.run("investigation", investigator.run, Scan(document=document, leads=findings[:20], extra_text=extra_text))
            findings = sort_findings(_merge_facts(report.findings, findings))
            summary, summary_source = report.summary or None, "agent"
            investigation = {"model": report.model, "verdict": report.verdict, "steps": report.steps, "usage": report.usage}
        except Exception as exc:
            log.warning("Investigation failed, using rule-based result: %s", exc)
            usage = getattr(investigator, "usage", None)
            investigation = {"error": str(exc)[:300], "usage": usage(len(document.pages)) if callable(usage) else None}

    findings = findings[:MAX_FINDINGS]
    score = risk(findings)
    ran = _ran_checks(document)
    for page in pages_out:
        page["risk_score"] = risk([f for f in findings if f.page == page["number"]])

    return {
        "risk_score": score,
        "label": label(score),
        "summary": summary or rule_summary(findings, score, len(ran)),
        "summary_source": summary_source,
        "document": {"kind": document.kind, "page_count": len(document.pages), "metadata": document.metadata},
        "pages": pages_out,
        "findings": [f.to_dict(sizes, i + 1) for i, f in enumerate(findings)],
        "checks_passed": _checks(document, findings, ran),
        "investigation": investigation,
        "ocr": ocr,
        "timings_ms": timer.ms,
    }
