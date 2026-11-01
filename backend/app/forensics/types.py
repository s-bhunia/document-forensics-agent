from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Category(str, Enum):
    TYPOGRAPHY = "typography"
    INK = "ink"
    SHARPNESS = "sharpness"
    ALIGNMENT = "alignment"
    DIGITS = "digits"
    COPY_MOVE = "copy_move"
    COMPRESSION = "compression"
    NOISE = "noise"
    METADATA = "metadata"
    STRUCTURE = "structure"
    SEMANTIC = "semantic"


Box = tuple[int, int, int, int]


@dataclass
class Word:
    text: str
    box: Box
    line_id: str
    conf: float = 100.0
    features: dict[str, float] = field(default_factory=dict)

    @property
    def x(self) -> int:
        return self.box[0]

    @property
    def y(self) -> int:
        return self.box[1]

    @property
    def w(self) -> int:
        return self.box[2]

    @property
    def h(self) -> int:
        return self.box[3]

    @property
    def cx(self) -> float:
        return self.x + self.w / 2


@dataclass
class Page:
    number: int
    image: np.ndarray
    words: list[Word] = field(default_factory=list)
    from_text_layer: bool = False
    source_jpeg: bool = False

    @property
    def height(self) -> int:
        return int(self.image.shape[0])

    @property
    def width(self) -> int:
        return int(self.image.shape[1])

    def lines(self) -> dict[str, list[Word]]:
        grouped: dict[str, list[Word]] = {}
        for word in self.words:
            grouped.setdefault(word.line_id, []).append(word)
        for words in grouped.values():
            words.sort(key=lambda w: w.x)
        return grouped


@dataclass
class Finding:
    category: Category
    severity: Severity
    title: str
    detail: str
    page: int | None = None
    box: Box | None = None
    text: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, page_sizes: dict[int, tuple[int, int]], index: int) -> dict[str, Any]:
        norm = None
        if self.box is not None and self.page in page_sizes:
            pw, ph = page_sizes[self.page]
            x, y, w, h = self.box
            norm = [round(x / pw, 4), round(y / ph, 4), round(w / pw, 4), round(h / ph, 4)]
        return {
            "id": f"f{index}",
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "detail": self.detail,
            "page": self.page,
            "box": norm,
            "text": self.text,
            "evidence": {k: _plain(v) for k, v in self.evidence.items()},
        }


@dataclass
class Document:
    kind: str
    pages: list[Page]
    metadata: dict[str, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)


def _plain(value: Any) -> Any:
    if isinstance(value, (np.floating, float)):
        return round(float(value), 4)
    if isinstance(value, np.integer):
        return int(value)
    return value


def union_box(boxes: list[Box]) -> Box:
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return x0, y0, x1 - x0, y1 - y0
