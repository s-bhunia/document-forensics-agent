import { Bot, ChevronDown, FileText, ListChecks } from "lucide-react";
import type { AnalysisDetail, AnalysisResult } from "../api/types";
import { countBySeverity } from "../lib/findings";
import { SEVERITY_META, SEVERITY_ORDER } from "../lib/meta";
import { formatBytes, formatDateTime, formatDuration, formatUsdShort, humanize } from "../lib/format";
import { isInvestigationError } from "../lib/investigation";
import { LabelBadge } from "./Badges";
import { InvestigationFailedNotice } from "./InvestigationPanel";
import { RiskGauge } from "./RiskGauge";

const KIND_LABELS: Record<AnalysisResult["document"]["kind"], string> = {
  image: "Image",
  pdf: "PDF",
  docx: "Word document",
};

export function ResultHeader({ analysis, result }: { analysis: AnalysisDetail; result: AnalysisResult }) {
  const counts = countBySeverity(result.findings);
  const metadata = Object.entries(result.document.metadata ?? {});
  const timings = Object.entries(result.timings_ms ?? {});
  const usage = result.investigation?.usage ?? null;
  const totalMs = timings.reduce((sum, [, v]) => sum + (Number.isFinite(v) ? v : 0), 0);

  return (
    <section className="card p-5 sm:p-6" aria-labelledby="result-title">
      <div className="flex flex-col gap-6 md:flex-row md:items-start">
        <RiskGauge score={result.risk_score} label={result.label} />
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <LabelBadge label={result.label} />
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {KIND_LABELS[result.document.kind] ?? result.document.kind} · {result.document.page_count}{" "}
              {result.document.page_count === 1 ? "page" : "pages"} · {formatBytes(analysis.size_bytes)}
            </span>
          </div>
          <h1 id="result-title" className="break-words text-xl font-semibold tracking-tight sm:text-2xl">
            {analysis.filename}
          </h1>
          <div>
            <span
              className={
                result.summary_source === "agent"
                  ? "inline-flex items-center gap-1 rounded-md bg-violet-50 px-2 py-0.5 text-[11px] font-medium text-violet-700 dark:bg-violet-500/10 dark:text-violet-300"
                  : "inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300"
              }
            >
              {result.summary_source === "agent" ? (
                <Bot className="h-3 w-3" aria-hidden="true" />
              ) : (
                <ListChecks className="h-3 w-3" aria-hidden="true" />
              )}
              {result.summary_source === "agent" ? "AI investigation" : "Rule-based"}
            </span>
            {usage && (
              <span
                className="ml-2 inline-flex items-center rounded-md border border-slate-200 px-2 py-0.5 text-[11px] font-medium tabular-nums text-slate-500 dark:border-slate-700 dark:text-slate-400"
                title={`AI cost: ${formatUsdShort(usage.cost_usd)} total over ${usage.calls} calls`}
                data-testid="usage-chip"
              >
                ≈ {formatUsdShort(usage.cost_per_page_usd)} / page
              </span>
            )}
            <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-700 dark:text-slate-300">
              {result.summary}
            </p>
          </div>
          {result.investigation && isInvestigationError(result.investigation) && (
            <InvestigationFailedNotice investigation={result.investigation} compact />
          )}
          <dl className="flex flex-wrap gap-2 pt-1" aria-label="Findings by severity">
            {SEVERITY_ORDER.map((s) => (
              <div
                key={s}
                className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-sm dark:border-slate-800"
              >
                <span className={`h-2 w-2 rounded-full ${SEVERITY_META[s].dot}`} aria-hidden="true" />
                <dt className="text-slate-500 dark:text-slate-400">{SEVERITY_META[s].label}</dt>
                <dd className="font-semibold tabular-nums" data-testid={`count-${s}`}>
                  {counts[s]}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      <details className="group mt-6 rounded-lg border border-slate-200 dark:border-slate-800">
        <summary className="flex cursor-pointer list-none items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium focus-ring [&::-webkit-details-marker]:hidden">
          <FileText className="h-4 w-4 text-slate-400" aria-hidden="true" />
          File details & metadata
          <span className="text-xs font-normal text-slate-400">({metadata.length})</span>
          <ChevronDown className="ml-auto h-4 w-4 text-slate-400 transition-transform group-open:rotate-180" aria-hidden="true" />
        </summary>
        <div className="grid gap-6 border-t border-slate-200 px-4 py-4 text-sm dark:border-slate-800 md:grid-cols-2">
          <dl className="space-y-1.5">
            <Row term="Content type" value={analysis.content_type} />
            <Row term="Uploaded" value={formatDateTime(analysis.created_at)} />
            <Row term="Completed" value={formatDateTime(analysis.completed_at)} />
            {totalMs > 0 && <Row term="Processing time" value={formatDuration(totalMs)} />}
          </dl>
          {metadata.length === 0 ? (
            <p className="text-slate-500 dark:text-slate-400">No embedded metadata was found.</p>
          ) : (
            <dl className="space-y-1.5">
              {metadata.map(([k, v]) => (
                <Row key={k} term={humanize(k)} value={v} />
              ))}
            </dl>
          )}
        </div>
      </details>
    </section>
  );
}

function Row({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex gap-3">
      <dt className="w-36 shrink-0 text-slate-500 dark:text-slate-400">{term}</dt>
      <dd className="min-w-0 break-words font-mono text-xs leading-5 text-slate-800 dark:text-slate-200">{value}</dd>
    </div>
  );
}
