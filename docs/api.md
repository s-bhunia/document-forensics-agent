# API contract

Base path: `/api`. All responses are JSON unless noted.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | `{"status":"ok","llm_enabled":bool}` |
| POST | `/api/analyses` | multipart field `file`. Returns `201` with an `AnalysisSummary`. Accepts PNG, JPEG, WEBP, TIFF, BMP, PDF, DOCX up to 25 MB. `400` with `{"detail": "..."}` on unsupported or oversized files. |
| GET | `/api/analyses?page=1&page_size=20&q=text` | `{"items": AnalysisSummary[], "total": int, "page": int, "page_size": int}` newest first; `q` filters by filename. |
| GET | `/api/analyses/{id}` | `AnalysisDetail`. `404` if unknown. |
| DELETE | `/api/analyses/{id}` | `204`. |
| GET | `/api/analyses/{id}/files/{path}` | Binary artifact (PNG/JPEG) referenced by paths inside `result`, e.g. `pages/1.jpg`, `layers/1_ela.png`. |

Poll `GET /api/analyses/{id}` every 1.5 s while `status` is `queued` or `processing`.

## Types

```ts
type Status = "queued" | "processing" | "completed" | "failed";
type Label = "likely_authentic" | "suspicious" | "highly_risky";
type Severity = "high" | "medium" | "low" | "info";
type Category =
  | "typography" | "ink" | "sharpness" | "alignment" | "digits"
  | "copy_move" | "compression" | "noise" | "metadata" | "structure" | "semantic";

interface AnalysisSummary {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: Status;
  risk_score: number | null;   // 0..1
  label: Label | null;
  finding_count: number | null;
  created_at: string;          // ISO 8601
  completed_at: string | null;
  error: string | null;
}

interface AnalysisDetail extends AnalysisSummary {
  result: AnalysisResult | null;
}

interface AnalysisResult {
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
  investigation: Investigation | null;   // null when no LLM is configured
  ocr: { page: number; lines: { text: string; box: Box }[] }[];
  timings_ms: Record<string, number>;
}

interface PageInfo {
  number: number;               // 1-based
  width: number;                // pixels of the page image
  height: number;
  image: string;                // artifact path, e.g. "pages/1.jpg"
  layers: { ela?: string; noise?: string };
  risk_score: number;
}

type Investigation =
  | { model: string; verdict: Label; steps: { tool: string; input: string; ok: boolean }[]; usage: Usage | null }
  | { error: string; usage: Usage | null };   // the AI step failed; result is rule-based

interface Usage {
  calls: number;               // LLM requests made
  input_tokens: number;        // everything sent, incl. images and history
  cached_tokens: number;       // part of input billed at the cached rate
  output_tokens: number;       // billable output, incl. thinking
  thinking_tokens: number;
  total_tokens: number;
  cost_usd: number;
  cost_per_page_usd: number;
  prices_per_million: { input: number; cached_input: number; output: number };
}

type Box = [number, number, number, number]; // x, y, width, height as fractions 0..1 of the page

interface Finding {
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
```
