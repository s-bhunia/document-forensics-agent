import clsx from "clsx";
import { useEffect, useState } from "react";
import { Check, Loader2 } from "lucide-react";
import type { Status } from "../api/types";

const STEPS = [
  { key: "uploaded", label: "Uploaded", hint: "File received" },
  { key: "queued", label: "Queued", hint: "Waiting for an analysis worker" },
  { key: "processing", label: "Analyzing", hint: "Rendering pages, running forensic checks and OCR" },
  { key: "report", label: "Report", hint: "Scoring findings and writing the summary" },
] as const;

export const AI_NOTICE_DELAY_MS = 10_000;

export function ProcessingState({ status, filename }: { status: Status; filename: string }) {
  const activeIndex = status === "queued" ? 1 : 2;
  const [longRunning, setLongRunning] = useState(false);

  useEffect(() => {
    if (status !== "processing") {
      setLongRunning(false);
      return;
    }
    const t = window.setTimeout(() => setLongRunning(true), AI_NOTICE_DELAY_MS);
    return () => window.clearTimeout(t);
  }, [status]);

  const heading =
    status === "queued"
      ? "Waiting in queue"
      : longRunning
        ? "AI examiner is investigating…"
        : "Analyzing document";
  return (
    <div className="card mx-auto max-w-xl p-6 sm:p-8" aria-live="polite">
      <div className="flex items-center gap-3">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
        <div className="min-w-0">
          <h1 className="text-lg font-semibold">{heading}</h1>
          <p className="truncate text-sm text-slate-500 dark:text-slate-400" title={filename}>
            {filename}
          </p>
        </div>
      </div>
      <ol className="mt-8 space-y-5" aria-label="Analysis progress">
        {STEPS.map((step, i) => {
          const done = i < activeIndex;
          const active = i === activeIndex;
          return (
            <li key={step.key} className="flex items-start gap-3" aria-current={active ? "step" : undefined}>
              <span
                className={clsx(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                  done && "bg-indigo-600 text-white dark:bg-indigo-500",
                  active && "bg-indigo-50 text-indigo-700 ring-2 ring-indigo-500 dark:bg-indigo-500/15 dark:text-indigo-300",
                  !done && !active && "bg-slate-100 text-slate-400 dark:bg-slate-800",
                )}
              >
                {done ? (
                  <Check className="h-4 w-4" aria-hidden="true" />
                ) : active ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  i + 1
                )}
              </span>
              <div>
                <p className={clsx("text-sm font-medium", !done && !active && "text-slate-400 dark:text-slate-500")}>
                  {step.label}
                  <span className="sr-only">{done ? " (done)" : active ? " (in progress)" : " (pending)"}</span>
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {active && step.key === "processing" && longRunning
                    ? "The AI examiner is inspecting regions with forensic tools"
                    : step.hint}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
      {longRunning && (
        <p className="mt-8 rounded-lg bg-violet-50 px-3 py-2 text-sm text-violet-800 dark:bg-violet-500/10 dark:text-violet-200">
          AI examiner is investigating… this can take a few minutes.
        </p>
      )}
      <p className={clsx("text-xs text-slate-500 dark:text-slate-400", longRunning ? "mt-3" : "mt-8")}>
        This page updates automatically. Analyses take up to 4 minutes when the AI examiner is enabled.
      </p>
    </div>
  );
}
