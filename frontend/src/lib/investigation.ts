import type { Investigation, InvestigationError } from "../api/types";
import { humanize } from "./format";

export function isInvestigationError(inv: Investigation): inv is InvestigationError {
  return "error" in inv;
}

const TOOL_LABELS: Record<string, string> = {
  view_page: "Viewed page",
  zoom: "Zoomed into region",
  read_text: "Read text",
  measure: "Measured region",
  compare: "Compared regions",
  find_peers: "Compared with peers",
  digit_widths: "Measured digit widths",
  region_forensics: "Ran region forensics",
  validate: "Validated identifiers",
  submit_report: "Submitted report",
};

export function toolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? humanize(tool);
}

/** Evidence keys that annotate a finding rather than describe what was measured. */
export const META_EVIDENCE_KEYS = new Set(["source", "grounded"]);

export function isUngrounded(evidence: Record<string, number | string> | undefined): boolean {
  return evidence?.grounded === "no";
}
