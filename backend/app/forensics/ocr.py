from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import pytesseract
from skimage.filters import threshold_sauvola

from app.forensics.types import Word

MIN_CONF = 50.0
TARGET_SIDE = 1800
PASSES = (("gray", 3), ("gray", 6), ("darkest", 6), ("sauvola", 11), ("flat", 11))


def _variants(rgb: np.ndarray, scale: float) -> dict[str, np.ndarray]:
    def up(img: np.ndarray) -> np.ndarray:
        return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC) if scale != 1.0 else img

    gray = up(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
    window = max(15, int(min(gray.shape) / 40) | 1)
    sauvola = ((gray > threshold_sauvola(gray, window_size=window, k=0.2)) * 255).astype(np.uint8)
    background = cv2.medianBlur(gray, max(31, window * 2 + 1))
    flat = cv2.normalize(cv2.divide(gray, background, scale=255), None, 0, 255, cv2.NORM_MINMAX)
    return {"gray": gray, "darkest": up(rgb.min(axis=2)), "sauvola": sauvola, "flat": flat}


def _run(image: np.ndarray, psm: int, lang: str, scale: float) -> list[Word]:
    data = pytesseract.image_to_data(image, lang=lang, config=f"--oem 1 --psm {psm}", output_type=pytesseract.Output.DICT)
    words = []
    for i, text in enumerate(data["text"]):
        text = (text or "").strip()
        conf = float(data["conf"][i])
        if not text or conf < MIN_CONF or not any(c.isalnum() for c in text):
            continue
        box = tuple(int(round(data[k][i] / scale)) for k in ("left", "top", "width", "height"))
        if box[2] >= 3 and box[3] >= 5:
            words.append(Word(text=text, box=box, line_id="", conf=conf))
    return words


def _overlap(a: tuple, b: tuple) -> float:
    ix = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / max(min(a[2] * a[3], b[2] * b[3]), 1)


def merge_words(candidates: list[Word]) -> list[Word]:
    kept: list[Word] = []
    for word in sorted(candidates, key=lambda w: (-w.conf, -len(w.text))):
        if all(_overlap(word.box, k.box) < 0.5 for k in kept):
            kept.append(word)
    return kept


def assign_lines(words: list[Word]) -> list[Word]:
    bands: list[list[Word]] = []
    for word in sorted(words, key=lambda w: w.y + w.h / 2):
        cy = word.y + word.h / 2
        for band in bands:
            ref_h = float(np.median([w.h for w in band]))
            ref_cy = float(np.median([w.y + w.h / 2 for w in band]))
            if abs(cy - ref_cy) <= 0.45 * max(ref_h, word.h):
                band.append(word)
                break
        else:
            bands.append([word])

    index = 0
    for band in bands:
        band.sort(key=lambda w: w.x)
        limit = 2.5 * float(np.median([w.h for w in band]))
        previous = None
        for word in band:
            if previous is not None and word.x - (previous.x + previous.w) > limit:
                index += 1
            word.line_id = f"l{index}"
            previous = word
        index += 1
    return words


def extract_words(rgb: np.ndarray, lang: str = "eng") -> list[Word]:
    longest = max(rgb.shape[:2])
    scale = min(TARGET_SIDE / longest, 3.0) if longest < TARGET_SIDE else 1.0
    variants = _variants(rgb, scale)
    with ThreadPoolExecutor(max_workers=len(PASSES)) as pool:
        results = pool.map(lambda p: _run(variants[p[0]], p[1], lang, scale), PASSES)
    return assign_lines(merge_words([w for ws in results for w in ws]))


def group_lines(words: list[Word]) -> list[dict]:
    lines: dict[str, list[Word]] = {}
    for word in words:
        lines.setdefault(word.line_id, []).append(word)
    out = []
    for items in lines.values():
        items.sort(key=lambda w: w.x)
        x0 = min(w.x for w in items)
        y0 = min(w.y for w in items)
        x1 = max(w.x + w.w for w in items)
        y1 = max(w.y + w.h for w in items)
        out.append({"text": " ".join(w.text for w in items), "box": (x0, y0, x1 - x0, y1 - y0)})
    out.sort(key=lambda l: (l["box"][1], l["box"][0]))
    return out
