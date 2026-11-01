from __future__ import annotations

import base64
from dataclasses import dataclass, field
from functools import cached_property

import cv2
import numpy as np

from app.forensics import imageforensics as imf
from app.forensics.consistency import COLOR_DELTA, _cluster_by_scale, _color_groups, _shape, _width_peers
from app.forensics.types import Box, Document, Finding, Page, Word
from app.forensics.validators import validate_text

VIEW_SIDE = 1400
ZOOM_SIDE = 1000
MAX_LINES = 120

FEATURES = (
    ("stroke", "stroke_px", 0.15, False),
    ("weight", "weight", 0.22, False),
    ("modulation", "stroke_contrast", 0.05, True),
    ("cap_height", "letter_height_px", 0.12, False),
    ("scale", "size", 0.15, False),
    ("ink_width", "width_px", 0.025, False),
    ("contrast", "ink_darkness", 0.28, False),
    ("sharpness", "edge_sharpness", 0.35, False),
)


@dataclass
class Scan:
    document: Document
    leads: list[Finding]
    extra_text: str = ""


@dataclass
class ToolResult:
    text: str
    images: list[tuple[str, str]] = field(default_factory=list)


def _jpeg(rgb: np.ndarray, side: int) -> str:
    h, w = rgb.shape[:2]
    scale = side / max(h, w)
    if scale < 1:
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    elif scale > 1:
        factor = min(scale, 4.0)
        rgb = cv2.resize(rgb, (int(w * factor), int(h * factor)), interpolation=cv2.INTER_CUBIC)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def _fmt(value: float) -> str:
    return f"{value:.3f}" if abs(value) < 10 else f"{value:.1f}"


class Workspace:
    def __init__(self, scan: Scan):
        self.scan = scan
        self.document = scan.document
        self.pages = {p.number: p for p in scan.document.pages}
        self.words: dict[str, tuple[Page, Word]] = {}
        self.word_ids: dict[int, str] = {}
        for page in self.document.pages:
            ordered = sorted(page.lines().values(), key=lambda ws: (min(w.y for w in ws), min(w.x for w in ws)))
            i = 0
            for line in ordered:
                for word in line:
                    i += 1
                    wid = f"p{page.number}w{i}"
                    self.words[wid] = (page, word)
                    self.word_ids[id(word)] = wid
        self._ela: dict[int, np.ndarray] = {}
        self._copies: dict[int, list[Finding]] = {}
        self.measured: set[str] = set()
        self.regions: list[tuple[int, Box]] = []

    def page(self, number: int) -> Page:
        if number not in self.pages:
            raise ValueError(f"page {number} does not exist; pages are {sorted(self.pages)}")
        return self.pages[number]

    def norm_box(self, page: Page, box: Box) -> list[float]:
        x, y, w, h = box
        return [round(x / page.width, 4), round(y / page.height, 4), round(w / page.width, 4), round(h / page.height, 4)]

    def pixel_box(self, page: Page, box: list[float]) -> Box:
        if len(box) != 4:
            raise ValueError("box must be [x, y, width, height] as fractions of the page")
        x, y, w, h = (float(v) for v in box)
        x0, y0 = max(0.0, min(x, 1.0)), max(0.0, min(y, 1.0))
        x1, y1 = max(x0, min(x + w, 1.0)), max(y0, min(y + h, 1.0))
        px = (int(x0 * page.width), int(y0 * page.height), int((x1 - x0) * page.width), int((y1 - y0) * page.height))
        if px[2] < 4 or px[3] < 4:
            raise ValueError("box is too small")
        return px

    def resolve(self, ids: list[str]) -> list[tuple[str, Page, Word]]:
        out = []
        for wid in ids:
            if wid not in self.words:
                raise ValueError(f"unknown word id {wid}")
            page, word = self.words[wid]
            out.append((wid, page, word))
        return out

    def _line_text(self, page: Page, words: list[Word]) -> str:
        box = self.norm_box(page, (min(w.x for w in words), min(w.y for w in words),
                                   max(w.x + w.w for w in words) - min(w.x for w in words),
                                   max(w.y + w.h for w in words) - min(w.y for w in words)))
        items = " ".join(f"{self.word_ids[id(w)]}:{w.text!r}" for w in words)
        return f"[y={box[1]:.3f} x={box[0]:.3f}] {items}"

    def overview(self) -> str:
        doc = self.document
        parts = [
            f"Document kind: {doc.kind}. Pages: {len(doc.pages)}.",
            "Metadata: " + (", ".join(f"{k}={v}" for k, v in doc.metadata.items()) or "none"),
        ]
        for page in doc.pages:
            lines = sorted(page.lines().values(), key=lambda ws: (min(w.y for w in ws), min(w.x for w in ws)))
            parts.append(f"\nPage {page.number} ({page.width}x{page.height}px, {'text layer' if page.from_text_layer else 'OCR'}), "
                         f"{len(lines)} lines:")
            parts += [self._line_text(page, ws) for ws in lines[:MAX_LINES]]
            if len(lines) > MAX_LINES:
                parts.append(f"... {len(lines) - MAX_LINES} more lines, use read_text")
        if self.scan.extra_text:
            parts.append("\nDocument text (DOCX body):\n" + self.scan.extra_text[:4000])
        parts.append("\nAutomated leads (unverified hints from fixed detectors; often false on template styling):")
        if not self.scan.leads:
            parts.append("none")
        for i, lead in enumerate(self.scan.leads[:20], 1):
            loc = ""
            if lead.page and lead.box and lead.page in self.pages:
                loc = f" page {lead.page} box {self.norm_box(self.pages[lead.page], lead.box)}"
            key_ev = {k: v for k, v in list(lead.evidence.items())[:6]}
            parts.append(f"L{i} [{lead.severity.value}/{lead.category.value}] {lead.title}"
                         f"{' “' + lead.text + '”' if lead.text else ''}{loc} {key_ev}")
        return "\n".join(parts)

    def view_page(self, page: int) -> ToolResult:
        p = self.page(page)
        return ToolResult(f"Page {page} ({p.width}x{p.height}px).", [(f"page {page}", _jpeg(p.image, VIEW_SIDE))])

    def zoom(self, page: int, box: list[float]) -> ToolResult:
        p = self.page(page)
        x, y, w, h = self.pixel_box(p, box)
        mx, my = int(w * 0.06) + 4, int(h * 0.15) + 4
        x0, y0 = max(0, x - mx), max(0, y - my)
        crop = p.image[y0 : min(p.height, y + h + my), x0 : min(p.width, x + w + mx)]
        inside = [self.word_ids[id(wd)] + ":" + repr(wd.text) for wd in p.words
                  if wd.x >= x0 and wd.y >= y0 and wd.x + wd.w <= x0 + crop.shape[1] and wd.y + wd.h <= y0 + crop.shape[0]]
        note = f"Zoom page {page} box {box} ({crop.shape[1]}x{crop.shape[0]}px source). Words inside: {', '.join(inside[:40]) or 'none'}"
        return ToolResult(note, [(f"zoom p{page} {box}", _jpeg(crop, ZOOM_SIDE))])

    def read_text(self, page: int, start: int = 0, count: int = 80) -> ToolResult:
        p = self.page(page)
        lines = sorted(p.lines().values(), key=lambda ws: (min(w.y for w in ws), min(w.x for w in ws)))
        chunk = lines[max(start, 0) : max(start, 0) + min(count, 150)]
        return ToolResult("\n".join(self._line_text(p, ws) for ws in chunk) or "no lines")

    def measure(self, word_ids: list[str]) -> ToolResult:
        rows = ["id | text | ocr_conf | " + " | ".join(label for _, label, _, _ in FEATURES) + " | ink_Lab"]
        for wid, _, word in self.resolve(word_ids[:40]):
            self.measured.add(wid)
            f = word.features
            if not f:
                rows.append(f"{wid} | {word.text!r} | {word.conf:.0f} | not measurable (too small or low contrast)")
                continue
            values = " | ".join(_fmt(f[key]) if key in f else "-" for key, _, _, _ in FEATURES)
            rows.append(f"{wid} | {word.text!r} | {word.conf:.0f} | {values} | "
                        f"{f['ink_l']:.0f},{f['ink_a']:.0f},{f['ink_b']:.0f}")
        rows.append("stroke_contrast: thick/thin stroke variation (serif fonts higher). size: x-height-normalised letter size. "
                    "width_px only comparable between equal-format values.")
        return ToolResult("\n".join(rows))

    def compare(self, target_ids: list[str], peer_ids: list[str]) -> ToolResult:
        targets = [w for _, _, w in self.resolve(target_ids) if w.features]
        target_ids_set = {id(w) for w in targets}
        peers = [w for _, _, w in self.resolve(peer_ids) if w.features and id(w) not in target_ids_set]
        if not targets or len(peers) < 2:
            raise ValueError("need at least one measurable target and two measurable peers")
        self.measured.update(self.word_ids[id(w)] for w in targets + peers)
        rows = ["feature | target | peer_median | peer_spread | difference | stands_out"]
        for key, label, threshold, absolute in FEATURES:
            pv = np.array([w.features[key] for w in peers if key in w.features])
            tv = [w.features[key] for w in targets if key in w.features]
            if len(pv) < 2 or not tv:
                continue
            t, med = float(np.mean(tv)), float(np.median(pv))
            mad = float(np.median(np.abs(pv - med)))
            if absolute:
                diff, spread = t - med, mad
                diff_txt = f"{diff:+.3f}"
                stands = abs(diff) >= threshold and abs(diff) >= 3 * spread
            else:
                if med == 0:
                    continue
                diff, spread = (t - med) / med, mad / med
                diff_txt = f"{diff * 100:+.1f}%"
                stands = abs(diff) >= threshold and abs(diff) >= 3 * spread
            rows.append(f"{label} | {_fmt(t)} | {_fmt(med)} | {spread * (1 if absolute else 100):.2f}{'' if absolute else '%'} | {diff_txt} | {'YES' if stands else 'no'}")
        dist = [np.linalg.norm([t.features['ink_l'] - p.features['ink_l'], t.features['ink_a'] - p.features['ink_a'],
                                t.features['ink_b'] - p.features['ink_b']]) for t in targets for p in peers]
        rows.append(f"ink colour distance target-peers (Lab dE): median {np.median(dist):.1f} "
                    "(background colour can shift this; compare only over similar backgrounds)")
        rows.append("YES = difference beyond threshold and 3x the peers' own spread.")
        return ToolResult("\n".join(rows))

    def find_peers(self, word_id: str) -> ToolResult:
        (_, page, word), = self.resolve([word_id])
        line = [w for w in page.lines().get(word.line_id, []) if w is not word]
        out = [f"same line: {', '.join(self.word_ids[id(w)] + ':' + repr(w.text) for w in line) or 'none'}"]
        if word.features:
            measured = [w for w in page.words if w.features]
            style = []
            for group in _color_groups(measured):
                if word in group:
                    for cluster in _cluster_by_scale(group, ratio=1.3):
                        if word in cluster:
                            style = [w for w in cluster if w is not word]
            out.append(f"same colour and similar size ({len(style)}): "
                       + (", ".join(self.word_ids[id(w)] + ':' + repr(w.text) for w in style[:40]) or "none"))
        shape = _shape(word.text)
        if shape:
            same = [w for w in page.words if w is not word and _shape(w.text) == shape]
            out.append(f"same number format {shape!r}: " + (", ".join(self.word_ids[id(w)] + ':' + repr(w.text) for w in same) or "none"))
        return ToolResult("\n".join(out))

    def digit_widths(self, page: int) -> ToolResult:
        p = self.page(page)
        groups: dict[str, list[Word]] = {}
        for w in p.words:
            shape = _shape(w.text)
            if shape and w.features:
                groups.setdefault(shape, []).append(w)
        if not groups:
            return ToolResult("No formatted numbers (dates, amounts, IDs) with 6+ digits on this page.")
        rows = []
        for shape, items in groups.items():
            rows.append(f"format {shape!r}:")
            for w in sorted(items, key=lambda w: w.features["ink_width"]):
                self.measured.add(self.word_ids[id(w)])
                peers = _width_peers(w, items)
                verdict = "no comparable peers"
                if len(peers) >= 2:
                    others = np.array([p.features["ink_width"] for p in peers])
                    med = float(np.median(others))
                    diff = w.features["ink_width"] - med
                    spread = float(np.ptp(others))
                    outlier = abs(diff) >= 2 and abs(diff) / med >= 0.025 and spread < abs(diff)
                    verdict = (f"{'OUTLIER' if outlier else 'consistent'}: {diff:+.0f}px ({diff / med * 100:+.1f}%) vs "
                               f"{len(peers)} peers (median {med:.0f}px, peers' own spread {spread:.0f}px)")
                rows.append(f"  {self.word_ids[id(w)]} {w.text!r} width={w.features['ink_width']:.0f}px size={w.features['scale']:.1f} "
                            f"stroke={w.features['stroke']:.2f} -> {verdict}")
        rows.append("Printed digits are tabular: equal-format values in one font and size share one width. OUTLIER means "
                    "the peers agree with each other more closely than with this value; rasterisation does not cause that.")
        return ToolResult("\n".join(rows))

    def _ela_map(self, page: Page) -> np.ndarray:
        if page.number not in self._ela:
            bgr = cv2.cvtColor(page.image, cv2.COLOR_RGB2BGR)
            ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
            self._ela[page.number] = cv2.absdiff(bgr, cv2.imdecode(buf, cv2.IMREAD_COLOR)).astype(np.float32).mean(axis=2)
        return self._ela[page.number]

    def region_forensics(self, page: int, box: list[float]) -> ToolResult:
        p = self.page(page)
        x, y, w, h = self.pixel_box(p, box)
        self.regions.append((page, (x, y, w, h)))
        gray = cv2.cvtColor(p.image, cv2.COLOR_RGB2GRAY).astype(np.float32)
        grad = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
        ela = self._ela_map(p) / (grad / 8.0 + 2.0)
        residual = gray - cv2.medianBlur(gray.astype(np.uint8), 3).astype(np.float32)
        smooth = grad < 40
        region = (slice(y, y + h), slice(x, x + w))
        e_in, e_all = float(ela[region].mean()), float(ela.mean())
        if smooth[region].sum() > 50:
            n_in, n_all = float(residual[region][smooth[region]].std()), float(residual[smooth].std())
        else:
            n_in = n_all = float("nan")
        if p.number not in self._copies:
            self._copies[p.number] = [] if p.from_text_layer else imf.copy_move(p)
        hits = [f for f in self._copies[p.number] if f.box and _overlaps(f.box, (x, y, w, h))]
        lines = [
            f"error level (detail-normalised): region {e_in:.2f} vs page {e_all:.2f} (ratio {e_in / max(e_all, 1e-6):.2f}; >2 suggests different compression history)",
            f"background grain: region {n_in:.2f} vs page {n_all:.2f}" + ("" if np.isnan(n_in) else f" (ratio {n_in / max(n_all, 1e-6):.2f}; <0.5 or >2 is unusual)"),
            f"copy-move matches touching region: {len(hits)}" + "".join(f"\n  {f.detail}" for f in hits[:3]),
        ]
        if p.from_text_layer:
            lines.append("Note: page rendered from a PDF text layer; pixel statistics are not meaningful here.")
        return ToolResult("\n".join(lines))

    def validate(self, text: str) -> ToolResult:
        findings = validate_text(text)
        if not findings:
            return ToolResult("No ID checksum or calendar problems found in that text (PAN, Aadhaar, GSTIN, dates).")
        return ToolResult("\n".join(f"{f.title}: {f.detail}" for f in findings))

    @cached_property
    def leads_by_index(self) -> dict[int, Finding]:
        return {i: lead for i, lead in enumerate(self.scan.leads[:20], 1)}


def _overlaps(a: Box, b: Box) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


__all__ = ["Scan", "ToolResult", "Workspace", "COLOR_DELTA"]
