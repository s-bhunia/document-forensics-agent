import { Link } from "react-router-dom";
import { queryOptions, useQueries } from "@tanstack/react-query";
import { Layers, X } from "lucide-react";
import { ApiError, getAnalysis } from "../api/client";
import { queryKeys } from "../hooks/useAnalyses";
import { isActiveStatus } from "../lib/meta";
import { formatBytes } from "../lib/format";
import { LabelBadge, StatusBadge } from "./Badges";
import { FileIcon } from "./AnalysisRow";
import { Spinner } from "./Spinner";

export const BATCH_POLL_INTERVAL_MS = 3000;

export function BatchPanel({ ids, onClear }: { ids: string[]; onClear: () => void }) {
  const queries = useQueries({
    queries: ids.map((id) =>
      queryOptions({
        queryKey: queryKeys.detail(id),
        queryFn: () => getAnalysis(id),
        refetchInterval: (query) => (isActiveStatus(query.state.data?.status) ? BATCH_POLL_INTERVAL_MS : false),
        retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
      }),
    ),
  });

  const finished = queries.filter((q) => (q.data ? !isActiveStatus(q.data.status) : q.isError)).length;
  const allDone = finished === ids.length;

  return (
    <section className="card overflow-hidden" aria-labelledby="batch-heading">
      <div className="flex items-center gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <Layers className="h-4 w-4 text-indigo-500" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <h2 id="batch-heading" className="text-sm font-semibold">
            Batch
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400" aria-live="polite" data-testid="batch-progress">
            {allDone ? `All ${ids.length} finished` : `${finished} of ${ids.length} finished`}
          </p>
        </div>
        <button type="button" className="btn-ghost px-2.5 py-1 text-xs" onClick={onClear}>
          <X className="h-3.5 w-3.5" aria-hidden="true" />
          Clear
        </button>
      </div>
      <ul className="divide-y divide-slate-100 dark:divide-slate-800" aria-label="Batch analyses">
        {ids.map((id, i) => {
          const q = queries[i];
          const a = q.data;
          return (
            <li key={id} className="relative flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/40" data-testid={`batch-row-${id}`}>
              <div className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 min-[400px]:flex">
                <FileIcon contentType={a?.content_type ?? ""} className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <Link
                  to={`/analyses/${id}`}
                  className="block truncate text-sm font-medium after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-inset focus-visible:after:ring-indigo-500"
                  title={a?.filename}
                >
                  {a?.filename ?? (q.isError ? "Unavailable analysis" : "Loading…")}
                </Link>
                {a && (
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {formatBytes(a.size_bytes)}
                    {a.status === "completed" && a.finding_count != null && ` · ${a.finding_count} finding${a.finding_count === 1 ? "" : "s"}`}
                    {a.status === "failed" && a.error && ` · ${a.error}`}
                  </p>
                )}
                {!a && q.isError && (
                  <p className="text-xs text-red-600 dark:text-red-400">
                    {q.error instanceof ApiError && q.error.status === 404 ? "Deleted or not found" : q.error.message}
                  </p>
                )}
              </div>
              <div className="shrink-0">
                {a ? (
                  a.status === "completed" && a.label ? (
                    <LabelBadge label={a.label} riskScore={a.risk_score} />
                  ) : (
                    <StatusBadge status={a.status} />
                  )
                ) : q.isPending ? (
                  <Spinner className="h-4 w-4" label="Loading status" />
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
