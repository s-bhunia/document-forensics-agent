from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from app.forensics.textfeatures import alnum
from app.forensics.types import Category, Finding, Page, Severity, Word, union_box


@dataclass(frozen=True)
class Feature:
    key: str
    threshold: float
    label: str
    category: Category
    tall_only: bool = False
    absolute: bool = False


_COMMON = (
    Feature("modulation", 0.10, "stroke contrast (typeface)", Category.TYPOGRAPHY, absolute=True),
    Feature("contrast", 0.28, "ink darkness", Category.INK),
    Feature("sharpness", 0.35, "edge sharpness", Category.SHARPNESS),
)
MIN_CONF = 60.0
MIN_CONTRAST = 20.0
COLOR_DELTA = 15.0
LINE_FEATURES = (
    Feature("stroke", 0.15, "stroke weight", Category.TYPOGRAPHY),
    Feature("modulation", 0.05, "stroke contrast (typeface)", Category.TYPOGRAPHY, absolute=True),
    Feature("cap_height", 0.12, "letter height", Category.TYPOGRAPHY, tall_only=True),
) + _COMMON[1:]
GROUP_FEATURES = (
    Feature("weight", 0.22, "stroke weight", Category.TYPOGRAPHY),
    Feature("scale", 0.15, "text size", Category.TYPOGRAPHY),
) + _COMMON
GROUP_SCALE_RATIO = 1.3

SEED_CONF = 80.0
NOISE_MULTIPLIER = 2.5
LINE_FLAG = 2.4
LINE_PARTIAL = 0.6
SPAN_GROW = 1.0
GROUP_FLAG = 2.5
MAX_GROUP_OUTLIER_SHARE = 0.25


def _usable(word: Word) -> bool:
    return (
        bool(word.features)
        and len(alnum(word.text)) >= 2
        and word.conf >= MIN_CONF
        and word.features["contrast"] >= MIN_CONTRAST
    )


def _color_distance(a: Word, b: Word) -> float:
    fa, fb = a.features, b.features
    return float(np.linalg.norm([fa["ink_l"] - fb["ink_l"], fa["ink_a"] - fb["ink_a"], fa["ink_b"] - fb["ink_b"]]))


def _seedable(word: Word, score: float = 0.0) -> bool:
    length = len(alnum(word.text))
    return word.conf >= SEED_CONF and (length >= 3 or (length == 2 and score >= 3.0 and word.features["scale"] >= 18))


def _color_groups(words: list[Word]) -> list[list[Word]]:
    groups: list[tuple[np.ndarray, list[Word]]] = []
    for word in sorted(words, key=lambda w: w.features["ink_l"]):
        lab = np.array([word.features["ink_l"], word.features["ink_a"], word.features["ink_b"]])
        for centre, members in groups:
            if np.linalg.norm(lab - centre) <= COLOR_DELTA:
                members.append(word)
                centre[:] = np.mean([[m.features["ink_l"], m.features["ink_a"], m.features["ink_b"]] for m in members], axis=0)
                break
        else:
            groups.append((lab.astype(np.float64), [word]))
    return [members for _, members in groups]


def _deviation(feature: Feature, value: float, peers: np.ndarray, threshold: float) -> tuple[float, float, float] | None:
    med = float(np.median(peers))
    spread = float(np.median(np.abs(peers - med)))
    if feature.absolute:
        diff = value - med
        if spread > threshold * 0.6:
            return None
        return abs(diff) / threshold, med, diff
    if med <= 1e-6:
        return None
    if spread / med > threshold * 0.6:
        return None
    diff = (value - med) / med
    return abs(diff) / threshold, med, diff


def line_thresholds(page: Page) -> dict[str, float]:
    spreads: dict[str, list[float]] = {f.key: [] for f in LINE_FEATURES}
    for line in page.lines().values():
        words = [w for w in line if _usable(w)]
        if len(words) < 4:
            continue
        for feature in LINE_FEATURES:
            values = np.array([w.features[feature.key] for w in words if feature.key in w.features and (not feature.tall_only or w.features["tall"])])
            if len(values) < 3:
                continue
            med = float(np.median(values))
            mad = float(np.median(np.abs(values - med)))
            spreads[feature.key].append(mad if feature.absolute else mad / med if med > 1e-6 else 0.0)
    return {
        f.key: max(f.threshold, NOISE_MULTIPLIER * float(np.median(spreads[f.key]))) if spreads[f.key] else f.threshold
        for f in LINE_FEATURES
    }


def _score(word: Word, peers: list[Word], use_robust_z: bool, thresholds: dict[str, float] | None = None) -> tuple[float, list[dict]]:
    total = 0.0
    hits: list[dict] = []
    thresholds = thresholds or {}
    for feature in GROUP_FEATURES if use_robust_z else LINE_FEATURES:
        threshold = thresholds.get(feature.key, feature.threshold)
        pool = [p for p in peers if feature.key in p.features and (not feature.tall_only or p.features["tall"])]
        if feature.key not in word.features or len(pool) < 2:
            continue
        if feature.tall_only and not word.features["tall"]:
            continue
        values = np.array([p.features[feature.key] for p in pool], dtype=np.float64)
        value = word.features[feature.key]
        dev = _deviation(feature, value, values, threshold)
        if dev is None:
            continue
        ratio, med, diff = dev
        z = 0.0
        if use_robust_z:
            mad = float(np.median(np.abs(values - med))) * 1.4826
            floor = threshold * (1.0 if feature.absolute else abs(med)) * 0.25
            z = abs(value - med) / max(mad, floor, 1e-6)
            if z < 3.5:
                continue
        if ratio < (1.0 if use_robust_z else LINE_PARTIAL):
            continue
        total += min(ratio, 3.0)
        hits.append({"feature": feature, "value": value, "median": med, "diff": diff, "ratio": ratio, "z": z})
    return total, hits


def _group_flagged(score: float, hits: list[dict]) -> bool:
    if len(hits) < 2:
        return False
    return score >= GROUP_FLAG or any(h["z"] >= 5.0 and h["ratio"] >= 1.3 for h in hits)


def _is_flagged(score: float, hits: list[dict], flag: float) -> bool:
    return score >= flag and (len(hits) >= 2 or max(h["ratio"] for h in hits) >= 2.0)


def _same_direction(hits: list[dict], seed: list[dict]) -> bool:
    signs = {h["feature"].key: h["diff"] > 0 for h in seed}
    return any(h["feature"].key in signs and (h["diff"] > 0) == signs[h["feature"].key] for h in hits)


def _describe(hits: list[dict]) -> str:
    parts = []
    for hit in sorted(hits, key=lambda h: -h["ratio"]):
        f: Feature = hit["feature"]
        if f.absolute:
            direction = "higher" if hit["diff"] > 0 else "lower"
            parts.append(f"{f.label} is {direction} ({hit['value']:.2f} vs {hit['median']:.2f})")
        else:
            direction = "more" if hit["diff"] > 0 else "less"
            if f.key in ("weight", "stroke"):
                direction = "heavier" if hit["diff"] > 0 else "lighter"
            elif f.key == "cap_height":
                direction = "taller" if hit["diff"] > 0 else "shorter"
            elif f.key == "contrast":
                direction = "darker" if hit["diff"] > 0 else "lighter"
            elif f.key == "sharpness":
                direction = "sharper" if hit["diff"] > 0 else "blurrier"
            parts.append(f"{f.label} {abs(hit['diff']) * 100:.0f}% {direction}")
    return "; ".join(parts)


def _evidence(hits: list[dict]) -> dict:
    ev: dict = {}
    for hit in hits:
        key = hit["feature"].key
        ev[f"{key}"] = hit["value"]
        ev[f"{key}_peer_median"] = hit["median"]
    return ev


def _primary(hits: list[dict]) -> Category:
    return max(hits, key=lambda h: h["ratio"])["feature"].category


def _severity(score: float, flag: float) -> Severity:
    if score >= flag * 1.5:
        return Severity.HIGH
    return Severity.MEDIUM


def _merge_spans(flagged: list[tuple[Word, float, list[dict]]], line: list[Word]) -> list[list[tuple[Word, float, list[dict]]]]:
    order = {id(w): i for i, w in enumerate(line)}
    flagged.sort(key=lambda t: order[id(t[0])])
    spans: list[list] = []
    for item in flagged:
        if spans and order[id(item[0])] - order[id(spans[-1][-1][0])] == 1:
            spans[-1].append(item)
        else:
            spans.append([item])
    return spans


def line_consistency(page: Page) -> tuple[list[Finding], set[int]]:
    findings: list[Finding] = []
    flagged_ids: set[int] = set()
    thresholds = line_thresholds(page)
    for line in page.lines().values():
        words = [w for w in line if _usable(w)]
        if words:
            typical = float(np.median([w.h for w in words]))
            words = [w for w in words if w.h <= 1.6 * typical]
        if len(words) < 3:
            continue
        scored = []
        for word in words:
            peers = [p for p in words if p is not word and _color_distance(p, word) <= COLOR_DELTA * 1.5]
            scored.append((word, *_score(word, peers, use_robust_z=False, thresholds=thresholds)))
        seeds = {i for i, (w, score, hits) in enumerate(scored) if hits and _seedable(w, score) and _is_flagged(score, hits, LINE_FLAG)}
        if not seeds or len(seeds) > len(words) / 3:
            continue
        grown = set(seeds)
        for i in seeds:
            for step in (-1, 1):
                j = i + step
                while 0 <= j < len(scored) and j not in grown:
                    _, score, hits = scored[j]
                    if score < SPAN_GROW or not _same_direction(hits, scored[i][2]):
                        break
                    grown.add(j)
                    j += step
        if len(grown) > len(words) / 2:
            continue
        flagged = [scored[i] for i in sorted(grown)]
        for span in _merge_spans(flagged, words):
            span_words = [s[0] for s in span]
            best = max(span, key=lambda s: s[1])
            text = " ".join(w.text for w in span_words)
            flagged_ids.update(id(w) for w in span_words)
            findings.append(
                Finding(
                    category=_primary(best[2]),
                    severity=_severity(best[1], LINE_FLAG),
                    title="Text style changes within a line",
                    detail=f"“{text}” does not match the rest of its line: {_describe(best[2])}. "
                    "Words typed into an existing line rarely match the original print exactly.",
                    page=page.number,
                    box=union_box([w.box for w in span_words]),
                    text=text,
                    evidence={"score": best[1], **_evidence(best[2])},
                )
            )
    return findings, flagged_ids


def _cluster_by_scale(words: list[Word], ratio: float = 1.15) -> list[list[Word]]:
    ordered = sorted(words, key=lambda w: w.features["scale"])
    clusters: list[list[Word]] = []
    for word in ordered:
        if clusters:
            ref = float(np.median([w.features["scale"] for w in clusters[-1]]))
            if word.features["scale"] / ref <= ratio:
                clusters[-1].append(word)
                continue
        clusters.append([word])
    return clusters


def _is_emphasis(hits: list[dict]) -> bool:
    diffs = {h["feature"].key: h["diff"] for h in hits}
    return diffs.get("scale", 0) > 0 and diffs.get("weight", 0) >= 0


def _shared_by_peers(word: Word, hits: list[dict], peers: list[Word]) -> bool:
    top = max(hits, key=lambda h: h["ratio"])
    key, med, diff = top["feature"].key, top["median"], top["diff"]
    if top["feature"].absolute:
        similar = [p for p in peers if key in p.features and (p.features[key] - med) * diff > 0 and abs(p.features[key] - med) >= 0.6 * abs(diff)]
    else:
        similar = [
            p for p in peers
            if key in p.features and med and ((p.features[key] - med) / med) * diff > 0
            and abs((p.features[key] - med) / med) >= 0.6 * abs(diff)
        ]
    return len(similar) >= 2


def group_consistency(page: Page, skip: set[int]) -> list[Finding]:
    findings: list[Finding] = []
    for group in _color_groups([w for w in page.words if _usable(w)]):
        for cluster in _cluster_by_scale(group, ratio=GROUP_SCALE_RATIO):
            if len(cluster) < 5:
                continue
            flagged = []
            for word in cluster:
                peers = [p for p in cluster if p is not word]
                score, hits = _score(word, peers, use_robust_z=True)
                if not hits or not _seedable(word) or not _group_flagged(score, hits):
                    continue
                if _is_emphasis(hits) or _shared_by_peers(word, hits, peers):
                    continue
                flagged.append((word, score, hits))
            if not flagged or len(flagged) > max(1, MAX_GROUP_OUTLIER_SHARE * len(cluster)):
                continue
            for word, score, hits in flagged:
                if id(word) in skip:
                    continue
                findings.append(
                    Finding(
                        category=_primary(hits),
                        severity=_severity(score, GROUP_FLAG),
                        title="Text differs from same-style text",
                        detail=f"“{word.text}” differs from {len(cluster) - 1} other words of the same size and colour: "
                        f"{_describe(hits)}.",
                        page=page.number,
                        box=word.box,
                        text=word.text,
                        evidence={"score": score, "peers": len(cluster) - 1, **_evidence(hits)},
                    )
                )
    return findings


_NUMERIC = re.compile(r"^[\d.,/:\-]+$")


def _shape(text: str) -> str | None:
    core = text.strip("()[]:;.,")
    digits = sum(c.isdigit() for c in core)
    if not _NUMERIC.match(core) or digits < 6 or (digits == len(core) and digits < 8):
        return None
    return re.sub(r"\d", "d", core)


def _width_peers(word: Word, items: list[Word]) -> list[Word]:
    width, scale = word.features["ink_width"], word.features["scale"]
    return [
        p for p in items
        if p is not word
        and abs(p.features["ink_width"] / width - 1) <= 0.08
        and abs(p.features["scale"] - scale) <= max(2.0, 0.15 * scale)
        and abs(p.features["modulation"] - word.features["modulation"]) <= 0.12
    ]


def digit_width_consistency(page: Page) -> list[Finding]:
    findings: list[Finding] = []
    groups: dict[str, list[Word]] = {}
    for word in page.words:
        if not word.features or word.features["contrast"] < MIN_CONTRAST:
            continue
        shape = _shape(word.text)
        if shape:
            groups.setdefault(shape, []).append(word)

    for shape, items in groups.items():
        for group in _color_groups(items):
            for word in group:
                cluster = _width_peers(word, group)
                if len(cluster) < 2:
                    continue
                others = np.array([p.features["ink_width"] for p in cluster])
                width = word.features["ink_width"]
                med = float(np.median(others))
                diff = width - med
                rel = diff / med
                if abs(rel) < 0.025 or abs(diff) < 2 or np.ptp(others) >= abs(diff):
                    continue
                cluster = cluster + [word]
                findings.append(
                    Finding(
                        category=Category.DIGITS,
                        severity=Severity.HIGH if abs(rel) >= 0.03 else Severity.MEDIUM,
                        title="Number is a different width from matching numbers",
                        detail=f"“{word.text}” is {abs(rel) * 100:.1f}% {'wider' if diff > 0 else 'narrower'} than "
                        f"{len(cluster) - 1} other values in the same format ({width:.0f} px vs {med:.0f} px). "
                        "Printed digits share one width, so equal-format values should match exactly.",
                        page=page.number,
                        box=word.box,
                        text=word.text,
                        evidence={"width_px": width, "peer_median_px": med, "format": shape, "peers": len(cluster) - 1},
                    )
                )
    return findings


def baseline_consistency(page: Page, skip: set[int]) -> list[Finding]:
    findings: list[Finding] = []
    for line in page.lines().values():
        words = [w for w in line if _usable(w) and w.features["tall"]]
        if len(words) < 4:
            continue
        for word in words:
            if id(word) in skip:
                continue
            peers = [p for p in words if p is not word]
            xs = np.array([p.cx for p in peers])
            ys = np.array([p.features["baseline"] for p in peers])
            slope, intercept = np.polyfit(xs, ys, 1)
            residuals = ys - (slope * xs + intercept)
            cap = float(np.median([p.features["cap_height"] for p in peers]))
            if np.abs(residuals).max() > 0.08 * cap:
                continue
            offset = word.features["baseline"] - (slope * word.cx + intercept)
            if abs(offset) < 0.18 * cap or abs(offset) < 2:
                continue
            findings.append(
                Finding(
                    category=Category.ALIGNMENT,
                    severity=Severity.MEDIUM,
                    title="Word sits off the line",
                    detail=f"“{word.text}” sits {abs(offset):.1f} px {'lower' if offset > 0 else 'higher'} than the "
                    "line formed by the words around it.",
                    page=page.number,
                    box=word.box,
                    text=word.text,
                    evidence={"offset_px": offset, "cap_height_px": cap},
                )
            )
    return findings


def analyze_text_consistency(page: Page) -> list[Finding]:
    line_findings, flagged = line_consistency(page)
    findings = line_findings
    findings += group_consistency(page, flagged)
    findings += digit_width_consistency(page)
    findings += baseline_consistency(page, flagged)
    return findings
