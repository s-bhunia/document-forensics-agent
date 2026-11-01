import clsx from "clsx";
import {
  AlertTriangle,
  Bot,
  Eye,
  Flag,
  Hash,
  Ruler,
  Scale,
  ScanSearch,
  ShieldCheck,
  Type,
  Wrench,
  XCircle,
  ZoomIn,
  type LucideIcon,
} from "lucide-react";
import type { Investigation, InvestigationError } from "../api/types";
import { isInvestigationError, toolLabel } from "../lib/investigation";
import { LabelBadge } from "./Badges";
import { UsageCard } from "./UsageCard";

const TOOL_ICONS: Record<string, LucideIcon> = {
  view_page: Eye,
  zoom: ZoomIn,
  read_text: Type,
  measure: Ruler,
  compare: Scale,
  find_peers: Scale,
  digit_widths: Hash,
  region_forensics: ScanSearch,
  validate: ShieldCheck,
  submit_report: Flag,
};

export function InvestigationFailedNotice({
  investigation,
  compact,
  className,
}: {
  investigation: InvestigationError;
  compact?: boolean;
  className?: string;
}) {
  return (
    <div
      role="status"
      className={clsx(
        "flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200",
        compact ? "px-3 py-2 text-xs" : "p-4 text-sm",
        className,
      )}
    >
      <AlertTriangle className={clsx("shrink-0", compact ? "mt-px h-3.5 w-3.5" : "mt-0.5 h-4 w-4")} aria-hidden="true" />
      <div className="min-w-0">
        <p className="font-medium">AI investigation failed — showing rule-based result</p>
        <p className={clsx("break-words text-amber-800 dark:text-amber-300", compact ? "line-clamp-2" : "mt-1 font-mono text-xs")}>
          {investigation.error}
        </p>
      </div>
    </div>
  );
}

export function InvestigationPanel({ investigation }: { investigation: Investigation }) {
  if (isInvestigationError(investigation)) {
    return (
      <div className="space-y-4">
        <InvestigationFailedNotice investigation={investigation} />
        {investigation.usage && <UsageCard usage={investigation.usage} className="card" />}
      </div>
    );
  }

  const failed = investigation.steps.filter((s) => !s.ok).length;

  return (
    <section className="card p-5 sm:p-6" aria-labelledby="investigation-heading">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-300">
          <Bot className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 id="investigation-heading" className="text-base font-semibold">
            AI examiner
          </h2>
          <p className="truncate font-mono text-xs text-slate-500 dark:text-slate-400" title={investigation.model}>
            {investigation.model}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          Verdict
          <LabelBadge label={investigation.verdict} />
        </div>
      </div>

      {investigation.usage && <UsageCard usage={investigation.usage} className="mt-5" />}

      <p className="mt-5 text-sm text-slate-600 dark:text-slate-400">
        {investigation.steps.length} step{investigation.steps.length === 1 ? "" : "s"}
        {failed > 0 && `, ${failed} failed`}
      </p>

      {investigation.steps.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">The examiner did not use any tools.</p>
      ) : (
        <ol className="mt-4" aria-label="Investigation steps">
          {investigation.steps.map((step, i) => {
            const Icon = TOOL_ICONS[step.tool] ?? Wrench;
            const last = i === investigation.steps.length - 1;
            return (
              <li key={i} className="relative flex gap-3 pb-5 last:pb-0" data-testid="investigation-step" data-ok={step.ok}>
                {!last && (
                  <span
                    className="absolute left-4 top-9 -ml-px h-[calc(100%-2.25rem)] w-0.5 bg-slate-200 dark:bg-slate-800"
                    aria-hidden="true"
                  />
                )}
                <span
                  className={clsx(
                    "relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-4 ring-white dark:ring-slate-900",
                    step.ok
                      ? "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-300"
                      : "bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-300",
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {!step.ok && (
                    <XCircle
                      className="absolute -bottom-1 -right-1 h-4 w-4 rounded-full bg-white text-red-600 dark:bg-slate-900"
                      aria-hidden="true"
                    />
                  )}
                </span>
                <div className="min-w-0 flex-1 pt-1">
                  <p className="text-sm font-medium">
                    <span className="mr-1.5 tabular-nums text-slate-400">{i + 1}.</span>
                    {toolLabel(step.tool)}
                    {!step.ok && (
                      <span className="ml-2 rounded bg-red-50 px-1.5 py-0.5 text-[11px] font-medium text-red-700 dark:bg-red-500/10 dark:text-red-300">
                        Failed
                      </span>
                    )}
                  </p>
                  {step.input && (
                    <p className="mt-0.5 break-all font-mono text-xs text-slate-500 dark:text-slate-400">{step.input}</p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
