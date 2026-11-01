from __future__ import annotations

import cv2
import numpy as np
from skimage.morphology import skeletonize

from app.forensics.types import Page, Word

TALL_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789bdfhkl")
X_HEIGHT_RATIO = 0.72
_KERNEL = np.ones((3, 3), np.uint8)


def alnum(text: str) -> str:
    return "".join(c for c in text if c.isalnum())


def is_tall(text: str) -> bool:
    return any(c in TALL_CHARS for c in text)


def to_lab(rgb: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    lab[..., 0] *= 100.0 / 255.0
    lab[..., 1:] -= 128.0
    return lab


def ink_mask(gray: np.ndarray) -> np.ndarray:
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if mask.mean() > 255 * 0.6:
        mask = 255 - mask
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.zeros(count, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 3
    return keep[labels]


OVERSHOOT_CHARS = set("/\\()[]{}|")


def is_caps(text: str) -> bool:
    core = alnum(text)
    return bool(core) and all(c.isupper() or c.isdigit() for c in core)


def _row_extent(ink: np.ndarray) -> tuple[int, int, int] | None:
    rows = ink.sum(axis=1).astype(np.float32)
    if rows.max() == 0:
        return None
    any_rows = np.nonzero(rows >= 2)[0]
    core_rows = np.nonzero(rows >= 0.30 * rows.max())[0]
    if any_rows.size == 0:
        return None
    return int(any_rows[0]), int(core_rows[0]), int(core_rows[-1])


def measure_word(gray: np.ndarray, lab: np.ndarray, word: Word, pad: int = 3) -> dict[str, float] | None:
    x, y, w, h = word.box
    H, W = gray.shape
    x0, y0 = max(x - pad, 0), max(y - pad, 0)
    x1, y1 = min(x + w + pad, W), min(y + h + pad, H)
    g = gray[y0:y1, x0:x1]
    if g.size == 0 or min(g.shape) < 6:
        return None

    ink = ink_mask(g)
    if ink.sum() < 12:
        return None
    tall = is_tall(word.text) and not any(c in OVERSHOOT_CHARS for c in word.text)
    extent = _row_extent(ink)
    if extent is None:
        return None
    top_any, top_core, base = extent
    core_h = float(base - top_core + 1)
    if core_h < 5:
        return None
    top = top_any if tall else top_core
    cap = float(base - top + 1)
    scale = core_h if is_caps(word.text) else core_h / X_HEIGHT_RATIO

    ink_u8 = ink.astype(np.uint8)
    dt = cv2.distanceTransform(ink_u8, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    skeleton = skeletonize(ink)
    skel_vals = dt[skeleton]
    skel_vals = skel_vals[skel_vals > 0]
    if skel_vals.size < 4:
        return None
    stroke = float(ink.sum() / skeleton.sum())
    modulation = float(np.std(skel_vals) / (np.mean(skel_vals) + 1e-6))

    core = cv2.erode(ink_u8, _KERNEL).astype(bool)
    eroded = core.sum() >= 6
    if not eroded:
        core = ink
    background = ~cv2.dilate(ink_u8, _KERNEL, iterations=2).astype(bool)
    if background.sum() < 10:
        return None

    patch = lab[y0:y1, x0:x1]
    ink_lab = patch[core].mean(axis=0)
    bg_lab = np.median(patch[background], axis=0)

    gf = g.astype(np.float32)
    contrast_gray = float(np.median(gf[background]) - np.mean(gf[core]))
    gx = cv2.Sobel(gf, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gf, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.hypot(gx, gy)
    boundary = ink & ~core

    residual = gf - cv2.medianBlur(g, 3).astype(np.float32)
    noise = float(residual[background].std())

    cols = np.nonzero(ink.any(axis=0))[0]
    ink_width = float(cols[-1] - cols[0] + 1)
    n_chars = max(len(alnum(word.text)), 1)

    features = {
        "cap_height": cap,
        "tall": float(tall),
        "scale": scale,
        "stroke": stroke,
        "weight": stroke / scale,
        "modulation": modulation,
        "ink_l": float(ink_lab[0]),
        "contrast": float(bg_lab[0] - ink_lab[0]),
        "ink_da": float(ink_lab[1] - bg_lab[1]),
        "ink_db": float(ink_lab[2] - bg_lab[2]),
        "ink_chroma": float(np.hypot(ink_lab[1], ink_lab[2])),
        "ink_a": float(ink_lab[1]),
        "ink_b": float(ink_lab[2]),
        "noise": noise,
        "ink_width": ink_width,
        "char_width": ink_width / n_chars / scale,
        "top": float(y0 + top),
        "baseline": float(y0 + base),
        "left": float(x0 + cols[0]),
    }
    if eroded and boundary.sum() >= 8 and abs(contrast_gray) >= 15:
        features["sharpness"] = float(np.percentile(grad[boundary], 90) / abs(contrast_gray))
    return features


def measure_page(page: Page) -> None:
    rgb = page.image
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    lab = to_lab(rgb)
    for word in page.words:
        if len(alnum(word.text)) == 0:
            continue
        feats = measure_word(gray, lab, word)
        if feats:
            word.features = feats
