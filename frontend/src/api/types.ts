// Mirrors docs/api.md exactly.

export type Status = "queued" | "processing" | "completed" | "failed";
export type Label = "likely_authentic" | "suspicious" | "highly_risky";
export type Severity = "high" | "medium" | "low" | "info";
export type Category =
  | "typography"
  | "ink"
  | "sharpness"
  | "alignment"
  | "digits"
  | "copy_move"
  | "compression"
  | "noise"
  | "metadata"
  | "structure"
  | "semantic";

export interface Health {
  status: "ok";
  llm_enabled: boolean;
}

export interface AnalysisSummary {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: Status;
  risk_score: number | null; // 0..1
  label: Label | null;
  finding_count: number | null;
  created_at: string; // ISO 8601
  completed_at: string | null;
  error: string | null;
}

export interface AnalysisDetail extends AnalysisSummary {
  result: AnalysisResult | null;
}

export interface AnalysisList {
  items: AnalysisSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface AnalysisResult {
  risk_score: number;
  label: Label;
  summary: string;
  summary_source: "agent" | "rules";
  document: {
    kind: "image" | "pdf" | "docx";
    page_count: number;
    metadata: Record<string, string>;
  };
  pages: PageInfo[];
  findings: Finding[];
  checks_passed: string[];
  investigation: Investigation | null; // null when no LLM is configured
  ocr: OcrPage[];
  timings_ms: Record<string, number>;
}

export interface InvestigationStep {
  tool: string;
  input: string;
  ok: boolean;
}

export interface Usage {
  calls: number; // LLM requests made
  input_tokens: number; // everything sent, incl. images and history
  cached_tokens: number; // part of input billed at the cached rate
  output_tokens: number; // billable output, incl. thinking
  thinking_tokens: number;
  total_tokens: number;
  cost_usd: number;
  cost_per_page_usd: number;
  prices_per_million: { input: number; cached_input: number; output: number };
}

export interface InvestigationSuccess {
  model: string;
  verdict: Label;
  steps: InvestigationStep[];
  usage: Usage | null;
}

export interface InvestigationError {
  error: string; // the AI step failed; result is rule-based
  usage: Usage | null;
}

export type Investigation = InvestigationSuccess | InvestigationError;

export interface OcrPage {
  page: number;
  lines: { text: string; box: Box }[];
}

export interface PageInfo {
  number: number; // 1-based
  width: number; // pixels of the page image
  height: number;
  image: string; // artifact path, e.g. "pages/1.jpg"
  layers: { ela?: string; noise?: string };
  risk_score: number;
}

export type Box = [number, number, number, number]; // x, y, width, height as fractions 0..1 of the page

export interface Finding {
  id: string;
  category: Category;
  severity: Severity;
  title: string;
  detail: string;
  page: number | null;
  box: Box | null;
  text: string | null;
  evidence: Record<string, number | string>;
}
