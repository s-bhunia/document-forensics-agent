import type { AnalysisDetail, AnalysisSummary, Usage } from "../api/types";

export const usageFixture: Usage = {
  calls: 9,
  input_tokens: 34_210,
  cached_tokens: 12_000,
  output_tokens: 5_480,
  thinking_tokens: 3_100,
  total_tokens: 39_690,
  cost_usd: 0.1624,
  cost_per_page_usd: 0.0812,
  prices_per_million: { input: 3, cached_input: 0.3, output: 15 },
};

export const summaryFixture: AnalysisSummary = {
  id: "a1",
  filename: "payslip-march.png",
  content_type: "image/png",
  size_bytes: 482_133,
  status: "completed",
  risk_score: 0.72,
  label: "suspicious",
  finding_count: 3,
  created_at: "2026-10-30T10:00:00Z",
  completed_at: "2026-10-30T10:00:12Z",
  error: null,
};

export const completedFixture: AnalysisDetail = {
  ...summaryFixture,
  result: {
    risk_score: 0.72,
    label: "suspicious",
    summary: "The net pay amount appears to have been retyped in a different font.",
    summary_source: "agent",
    document: {
      kind: "image",
      page_count: 2,
      metadata: { software: "Adobe Photoshop 25.0", created: "2026:03:31 09:12:44" },
    },
    pages: [
      { number: 1, width: 1000, height: 1400, image: "pages/1.jpg", layers: { ela: "layers/1_ela.png", noise: "layers/1_noise.png" }, risk_score: 0.8 },
      { number: 2, width: 1000, height: 1400, image: "pages/2.jpg", layers: {}, risk_score: 0.1 },
    ],
    findings: [
      {
        id: "f1",
        category: "typography",
        severity: "high",
        title: "Font mismatch in net pay",
        detail: "Glyph shapes differ from surrounding digits.",
        page: 1,
        box: [0.1, 0.2, 0.3, 0.05],
        text: "4,250.00",
        evidence: { font_distance: 0.4312, baseline_shift_px: 3 },
      },
      {
        id: "f2",
        category: "metadata",
        severity: "medium",
        title: "Edited with image software",
        detail: "EXIF software tag indicates Photoshop.",
        page: null,
        box: null,
        text: null,
        evidence: { software: "Adobe Photoshop 25.0" },
      },
      {
        id: "f3",
        category: "compression",
        severity: "low",
        title: "Local compression anomaly",
        detail: "ELA response is higher in one region.",
        page: 2,
        box: [0.5, 0.5, 0.25, 0.1],
        text: null,
        evidence: { source: "agent", grounded: "no" },
      },
    ],
    checks_passed: ["Copy-move detection", "ID number checksums"],
    investigation: {
      model: "claude-vision-test",
      verdict: "suspicious",
      steps: [
        { tool: "view_page", input: "page=1", ok: true },
        { tool: "zoom", input: "page=1 box=[0.1,0.2,0.3,0.05]", ok: true },
        { tool: "find_peers", input: "text=4,250.00", ok: false },
        { tool: "submit_report", input: "3 findings", ok: true },
      ],
      usage: usageFixture,
    },
    ocr: [{ page: 1, lines: [{ text: "ACME Corp payslip", box: [0.1, 0.05, 0.4, 0.03] }] }],
    timings_ms: { render: 120, ocr: 800 },
  },
};

export const queuedFixture: AnalysisDetail = {
  ...summaryFixture,
  id: "q1",
  status: "queued",
  risk_score: null,
  label: null,
  finding_count: null,
  completed_at: null,
  result: null,
};

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
