from __future__ import annotations

from collections import defaultdict

from app.forensics.types import Finding, Severity

WEIGHTS = {Severity.HIGH: 0.45, Severity.MEDIUM: 0.2, Severity.LOW: 0.06, Severity.INFO: 0.0}
SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2, Severity.INFO: 3}
PER_CATEGORY = 3


def risk(findings: list[Finding]) -> float:
    by_category: dict[str, list[float]] = defaultdict(list)
    for finding in findings:
        by_category[finding.category.value].append(WEIGHTS[finding.severity])
    keep = 1.0
    for weights in by_category.values():
        for i, weight in enumerate(sorted(weights, reverse=True)[:PER_CATEGORY]):
            keep *= 1.0 - weight * (0.6**i)
    return round(min(1.0 - keep, 0.99), 4)


def label(score: float) -> str:
    if score >= 0.6:
        return "highly_risky"
    if score >= 0.2:
        return "suspicious"
    return "likely_authentic"


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda f: (SEVERITY_ORDER[f.severity], f.page or 0, (f.box or (0, 0))[1], (f.box or (0, 0))[0]),
    )


def rule_summary(findings: list[Finding], score: float, check_count: int) -> str:
    material = [f for f in findings if f.severity != Severity.INFO]
    if not material:
        return f"No signs of editing were found across {check_count} checks."
    verdict = {
        "highly_risky": "Strong signs of editing were found.",
        "suspicious": "Some warning signs were found; a person should review this document.",
        "likely_authentic": "Only minor irregularities were found.",
    }[label(score)]
    top = []
    for finding in material[:3]:
        top.append(f"{finding.title} (“{finding.text}”)" if finding.text else finding.title)
    return f"{verdict} Main points: " + "; ".join(top) + "."
