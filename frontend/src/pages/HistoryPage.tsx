import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, Inbox, Search } from "lucide-react";
import type { AnalysisSummary } from "../api/types";
import { AnalysisRow } from "../components/AnalysisRow";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ErrorAlert, errorMessage } from "../components/ErrorAlert";
import { Spinner } from "../components/Spinner";
import { useAnalysesList, useDeleteAnalysis } from "../hooks/useAnalyses";

const PAGE_SIZE = 20;

export function HistoryPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [search, setSearch] = useState(q);
  const [pendingDelete, setPendingDelete] = useState<AnalysisSummary | null>(null);

  useEffect(() => setSearch(q), [q]);

  useEffect(() => {
    if (search === q) return;
    const t = window.setTimeout(() => {
      const next = new URLSearchParams();
      if (search.trim()) next.set("q", search.trim());
      setParams(next, { replace: true });
    }, 300);
    return () => window.clearTimeout(t);
  }, [search, q, setParams]);

  const list = useAnalysesList({ page, pageSize: PAGE_SIZE, q });
  const del = useDeleteAnalysis();

  const total = list.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  useEffect(() => {
    if (list.data && list.data.items.length === 0 && page > 1 && total > 0) {
      const next = new URLSearchParams(params);
      next.set("page", String(totalPages));
      setParams(next, { replace: true });
    }
  }, [list.data, page, total, totalPages, params, setParams]);

  const goTo = (p: number) => {
    const next = new URLSearchParams(params);
    if (p <= 1) next.delete("page");
    else next.set("page", String(p));
    setParams(next);
    window.scrollTo?.({ top: 0 });
  };

  const confirmDelete = () => {
    if (!pendingDelete) return;
    del.mutate(pendingDelete.id, { onSettled: () => setPendingDelete(null) });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">History</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">Every document you've analyzed, newest first.</p>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <label htmlFor="history-search" className="sr-only">
            Search by filename
          </label>
          <input
            id="history-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by filename"
            className="input pl-9"
          />
        </div>
      </div>

      {del.isError && (
        <ErrorAlert title="Couldn't delete analysis" onDismiss={() => del.reset()}>
          {errorMessage(del.error)}
        </ErrorAlert>
      )}

      {list.isPending ? (
        <div className="card flex justify-center p-12">
          <Spinner label="Loading analyses" />
        </div>
      ) : list.isError ? (
        <ErrorAlert
          title="Couldn't load analyses"
          action={
            <button type="button" className="btn-secondary py-1" onClick={() => list.refetch()}>
              Retry
            </button>
          }
        >
          {errorMessage(list.error)}
        </ErrorAlert>
      ) : list.data.items.length === 0 ? (
        <div className="card flex flex-col items-center px-6 py-16 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-slate-800">
            <Inbox className="h-6 w-6" aria-hidden="true" />
          </div>
          {q ? (
            <>
              <h2 className="mt-4 font-semibold">No matches for “{q}”</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Try a different part of the filename.</p>
            </>
          ) : (
            <>
              <h2 className="mt-4 font-semibold">No analyses yet</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Upload a document to check it for signs of editing.
              </p>
              <Link to="/" className="btn-primary mt-5">
                Analyze a document
              </Link>
            </>
          )}
        </div>
      ) : (
        <>
          <ul
            className="card divide-y divide-slate-100 overflow-hidden dark:divide-slate-800"
            aria-busy={list.isFetching || undefined}
          >
            {list.data.items.map((a) => (
              <AnalysisRow key={a.id} analysis={a} onDelete={setPendingDelete} />
            ))}
          </ul>
          <nav className="flex items-center justify-between gap-4 text-sm" aria-label="Pagination">
            <p className="text-slate-500 dark:text-slate-400">
              {total === 0
                ? "0 results"
                : `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, total)} of ${total}`}
            </p>
            {totalPages > 1 && (
              <div className="flex items-center gap-2">
                <button type="button" className="btn-secondary px-3 py-1.5" disabled={page <= 1} onClick={() => goTo(page - 1)}>
                  <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                  <span className="hidden sm:inline">Previous</span>
                </button>
                <span className="tabular-nums text-slate-600 dark:text-slate-300">
                  {page} / {totalPages}
                </span>
                <button
                  type="button"
                  className="btn-secondary px-3 py-1.5"
                  disabled={page >= totalPages}
                  onClick={() => goTo(page + 1)}
                >
                  <span className="hidden sm:inline">Next</span>
                  <ChevronRight className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            )}
          </nav>
        </>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete this analysis?"
        message={pendingDelete ? `“${pendingDelete.filename}” and its results will be permanently removed.` : ""}
        busy={del.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
