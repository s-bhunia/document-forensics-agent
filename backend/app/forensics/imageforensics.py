from __future__ import annotations

from collections import defaultdict

import cv2
import numpy as np
from scipy import ndimage

from app.forensics.types import Box, Category, Finding, Page, Severity

BLOCK = 16
NOISE_BLOCK = 32


def _gray(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def _heat(values: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    v = values.astype(np.float32)
    hi = float(np.percentile(v, 99.5)) or 1.0
    norm = np.clip(v / hi * 255.0, 0, 255).astype(np.uint8)
    norm = cv2.resize(norm, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST if v.shape != shape else cv2.INTER_LINEAR)
    return cv2.cvtColor(cv2.applyColorMap(norm, cv2.COLORMAP_INFERNO), cv2.COLOR_BGR2RGB)


def _block_mean(values: np.ndarray, block: int) -> np.ndarray:
    h, w = values.shape[0] // block, values.shape[1] // block
    if h == 0 or w == 0:
        return np.zeros((1, 1), np.float32)
    trimmed = values[: h * block, : w * block]
    return trimmed.reshape(h, block, w, block).mean(axis=(1, 3))


def _robust_z(values: np.ndarray) -> np.ndarray:
    med = np.median(values)
    mad = np.median(np.abs(values - med)) * 1.4826
    return (values - med) / max(mad, 1e-6)


def _components(mask: np.ndarray, block: int, min_blocks: int) -> list[Box]:
    labels, count = ndimage.label(mask)
    boxes = []
    for sl in ndimage.find_objects(labels):
        if sl is None:
            continue
        region = labels[sl] > 0
        if region.sum() < min_blocks:
            continue
        y0, y1 = sl[0].start, sl[0].stop
        x0, x1 = sl[1].start, sl[1].stop
        boxes.append((x0 * block, y0 * block, (x1 - x0) * block, (y1 - y0) * block))
    return boxes


def _peak(z: np.ndarray, box: Box, block: int) -> float:
    region = z[box[1] // block : (box[1] + box[3]) // block, box[0] // block : (box[0] + box[2]) // block]
    return float(region.max()) if region.size else 0.0


def error_level(page: Page, quality: int = 90) -> tuple[np.ndarray, list[Finding]]:
    bgr = cv2.cvtColor(page.image, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    recompressed = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    ela = cv2.absdiff(bgr, recompressed).astype(np.float32).mean(axis=2)
    layer = _heat(cv2.GaussianBlur(ela, (0, 0), 1.5), ela.shape)

    gray = _gray(page.image).astype(np.float32)
    grad = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    ratio = _block_mean(ela, BLOCK) / (_block_mean(grad, BLOCK) / 8.0 + 2.0)
    if ratio.size < 64:
        return layer, []
    z = _robust_z(ratio)
    mask = (z > 6.0) & (ratio > 2.5 * np.median(ratio))
    findings = []
    for box in sorted(_components(mask, BLOCK, 4), key=lambda b: -b[2] * b[3])[:3]:
        if box[2] * box[3] > 0.5 * page.width * page.height:
            continue
        findings.append(
            Finding(
                category=Category.COMPRESSION,
                severity=Severity.LOW,
                title="Compression differs in this area",
                detail="This region reacts differently to re-compression than the rest of the page, which can "
                "happen when content is pasted in from another image.",
                page=page.number,
                box=box,
                evidence={"peak_z": _peak(z, box, BLOCK)},
            )
        )
    return layer, findings


def noise_map(page: Page) -> tuple[np.ndarray, list[Finding]]:
    gray = _gray(page.image)
    residual = gray.astype(np.float32) - cv2.medianBlur(gray, 3).astype(np.float32)
    grad = cv2.magnitude(
        cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 1, 0), cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 0, 1)
    )
    smooth = (grad < 40).astype(np.float32)
    sq = _block_mean(residual**2 * smooth, NOISE_BLOCK)
    cover = _block_mean(smooth, NOISE_BLOCK)
    valid = cover > 0.5
    sigma = np.sqrt(np.where(valid, sq / np.maximum(cover, 1e-6), 0))
    layer = _heat(sigma, gray.shape)
    if valid.sum() < 48:
        return layer, []

    log_sigma = np.log(sigma + 0.3)
    z = np.zeros_like(log_sigma)
    z[valid] = _robust_z(log_sigma[valid])
    findings = []
    for direction, mask in (("higher", (z > 4.5) & valid), ("lower", (z < -4.5) & valid)):
        for box in sorted(_components(mask, NOISE_BLOCK, 3), key=lambda b: -b[2] * b[3])[:2]:
            if box[2] * box[3] > 0.35 * page.width * page.height:
                continue
            findings.append(
                Finding(
                    category=Category.NOISE,
                    severity=Severity.LOW,
                    title="Background grain differs in this area",
                    detail=f"The fine grain here is clearly {direction} than elsewhere on the page. Retouched or "
                    "pasted areas often lose or gain grain compared with the original capture.",
                    page=page.number,
                    box=box,
                    evidence={"direction": direction},
                )
            )
    return layer, findings


def _non_text_mask(page: Page) -> np.ndarray:
    mask = np.full((page.height, page.width), 255, np.uint8)
    for word in page.words:
        x, y, w, h = word.box
        cv2.rectangle(mask, (x - 4, y - 4), (x + w + 4, y + h + 4), 0, -1)
    return mask


def _sift(page: Page, mask: np.ndarray, n: int = 3000):
    sift = cv2.SIFT_create(nfeatures=n)
    return sift.detectAndCompute(_gray(page.image), mask)


def _bbox(points: np.ndarray) -> Box:
    x0, y0 = points.min(axis=0)
    x1, y1 = points.max(axis=0)
    return int(x0) - 6, int(y0) - 6, int(x1 - x0) + 12, int(y1 - y0) + 12


def _boxes_overlap(a: Box, b: Box) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def copy_move(page: Page, min_pairs: int = 15) -> list[Finding]:
    keypoints, desc = _sift(page, _non_text_mask(page))
    if desc is None or len(keypoints) < 20:
        return []
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    pts = np.array([k.pt for k in keypoints], np.float32)
    clusters: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    min_dist = max(30.0, 0.03 * max(page.width, page.height))
    for matches in matcher.knnMatch(desc, desc, k=3):
        if len(matches) < 3:
            continue
        _, m1, m2 = matches
        if m1.distance >= 0.6 * m2.distance:
            continue
        a, b = m1.queryIdx, m1.trainIdx
        if a > b:
            a, b = b, a
        d = pts[b] - pts[a]
        if np.hypot(*d) < min_dist:
            continue
        clusters[(int(round(d[0] / 6)), int(round(d[1] / 6)))].append((a, b))

    findings = []
    for (dx, dy), pairs in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        pairs = list(set(pairs))
        if len(pairs) < min_pairs:
            break
        src = _bbox(pts[[p[0] for p in pairs]])
        dst = _bbox(pts[[p[1] for p in pairs]])
        if src[2] < 12 or src[3] < 12 or _boxes_overlap(src, dst):
            continue
        if src[2] * src[3] > 0.15 * page.width * page.height:
            continue
        severity = Severity.HIGH if len(pairs) >= 30 else Severity.MEDIUM
        for box, role in ((dst, "copy"), (src, "source")):
            findings.append(
                Finding(
                    category=Category.COPY_MOVE,
                    severity=severity,
                    title="Duplicated image region",
                    detail=f"This area matches another part of the page ({len(pairs)} matching points, shifted by "
                    f"{dx * 6:+d}, {dy * 6:+d} px). Cloned stamps, signatures or patches leave this pattern.",
                    page=page.number,
                    box=box,
                    evidence={"matches": len(pairs), "role": role},
                )
            )
        if len(findings) >= 6:
            break
    return findings


def cross_page_copies(pages: list[Page], max_pages: int = 8) -> list[Finding]:
    raster = [p for p in pages[:max_pages] if not p.from_text_layer]
    if len(raster) < 2:
        return []
    feats = [(p, *_sift(p, _non_text_mask(p), 2000)) for p in raster]
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    findings = []
    for i in range(len(feats)):
        for j in range(i + 1, len(feats)):
            pa, ka, da = feats[i]
            pb, kb, db = feats[j]
            if da is None or db is None or len(ka) < 20 or len(kb) < 20:
                continue
            good = [m for m, n in (x for x in matcher.knnMatch(da, db, k=2) if len(x) == 2) if m.distance < 0.7 * n.distance]
            if len(good) < 25:
                continue
            src = np.float32([ka[m.queryIdx].pt for m in good])
            dst = np.float32([kb[m.trainIdx].pt for m in good])
            matrix, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=2.0)
            if matrix is None or inliers is None or inliers.sum() < 25:
                continue
            scale = float(np.hypot(matrix[0, 0], matrix[1, 0]))
            if abs(scale - 1) > 0.02:
                continue
            idx = inliers.ravel().astype(bool)
            box_a, box_b = _bbox(src[idx]), _bbox(dst[idx])
            x, y, w, h = box_a
            patch_a = _gray(pa.image)[max(y, 0) : y + h, max(x, 0) : x + w]
            warped = cv2.warpAffine(_gray(pb.image), cv2.invertAffineTransform(matrix), (pa.width, pa.height))
            patch_b = warped[max(y, 0) : y + h, max(x, 0) : x + w]
            if patch_a.size == 0 or patch_a.shape != patch_b.shape:
                continue
            diff = float(np.mean(cv2.absdiff(patch_a, patch_b)))
            if diff > 3.0:
                continue
            for page, box in ((pa, box_a), (pb, box_b)):
                findings.append(
                    Finding(
                        category=Category.COPY_MOVE,
                        severity=Severity.HIGH,
                        title="Identical region on two pages",
                        detail=f"This area is pixel-identical on pages {pa.number} and {pb.number} (mean difference "
                        f"{diff:.1f}/255). Scanned stamps and signatures never land exactly the same twice.",
                        page=page.number,
                        box=box,
                        evidence={"inliers": int(inliers.sum()), "mean_diff": diff},
                    )
                )
    return findings
