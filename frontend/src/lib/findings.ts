import type { Category, Finding, Severity } from "../api/types";
import { SEVERITY_ORDER } from "./meta";

export interface NumberedFinding extends Finding {
  number: number;
}

/** Numbers follow the backend's order so labels stay stable across filters and pages. */
export function numberFindings(findings: Finding[]): NumberedFinding[] {
  return findings.map((f, i) => ({ ...f, number: i + 1 }));
}

export function countBySeverity(findings: Finding[]): Record<Severity, number> {
  const counts: Record<Severity, number> = { high: 0, medium: 0, low: 0, info: 0 };
  for (const f of findings) counts[f.severity] = (counts[f.severity] ?? 0) + 1;
  return counts;
}

export interface FindingFilter {
  severities: Severity[]; // empty = all
  category: Category | "all";
}

export function filterFindings<T extends Finding>(findings: T[], filter: FindingFilter): T[] {
  return findings.filter(
    (f) =>
      (filter.severities.length === 0 || filter.severities.includes(f.severity)) &&
      (filter.category === "all" || f.category === filter.category),
  );
}

export function sortBySeverity<T extends Finding & { number: number }>(findings: T[]): T[] {
  return [...findings].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity) || a.number - b.number,
  );
}

export function presentCategories(findings: Finding[]): Category[] {
  return Array.from(new Set(findings.map((f) => f.category)));
}
