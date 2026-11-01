import { useEffect, useId, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Binary,
  Copy,
  FileSearch,
  Fingerprint,
  Focus,
  Hash,
  RotateCcw,
  Type,
  type LucideIcon,
} from "lucide-react";
import type { AnalysisSummary } from "../api/types";
import { BatchPanel } from "../components/BatchPanel";
import { Dropzone } from "../components/Dropzone";
import { ErrorAlert, errorMessage } from "../components/ErrorAlert";
import { AnalysisRow } from "../components/AnalysisRow";
import { SelectedFiles } from "../components/SelectedFiles";
import { Spinner } from "../components/Spinner";
import { useAnalysesList, queryKeys } from "../hooks/useAnalyses";
import { useBatch } from "../hooks/useBatch";
import { useUploadQueue } from "../hooks/useUploadQueue";

const CHECKS: { title: string; body: string; Icon: LucideIcon }[] = [
  { title: "Typography consistency", body: "Font, size and baseline mismatches between neighbouring characters and lines.", Icon: Type },
  { title: "Ink & sharpness", body: "Colour and edge-sharpness differences that betray pasted or retouched text.", Icon: Focus },
  { title: "Digit widths", body: "Amounts and dates whose glyph widths don't match the surrounding numerals.", Icon: Binary },
  { title: "Copy-move", body: "Regions duplicated from elsewhere in the same document.", Icon: Copy },
  { title: "Compression & noise", body: "Error-level and noise inconsistencies left behind by local edits.", Icon: Fingerprint },
  { title: "File metadata", body: "Editing software, timestamps and structural traces inside the file.", Icon: FileSearch },
  { title: "ID number checks", body: "Checksums and format rules for identifiers found in the text.", Icon: Hash },
];

export function AnalyzePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const errorId = useId();
  const queue = useUploadQueue();
  const batch = useBatch();
  const [busy, setBusy] = useState(false);
  const [batchMode, setBatchMode] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const recent = useAnalysesList({ page: 1, pageSize: 5 });
  const { items, rejected } = queue;

  useEffect(() => {
    if (items.length === 0) setBatchMode(false);
  }, [items.length]);

  const onFiles = (files: File[]) => {
    setUploadError(null);
    queue.addFiles(files);
  };

  const onCreatedInBatch = (created: AnalysisSummary) => batch.add(created.id);

  const runBatch = async (targets: typeof items) => {
    setBusy(true);
    setBatchMode(true);
    await queue.uploadMany(targets, onCreatedInBatch);
    setBusy(false);
    void queryClient.invalidateQueries({ queryKey: queryKeys.analyses });
  };

  const submit = async () => {
    if (busy || items.length === 0) return;
    setUploadError(null);
    if (items.length === 1 && !batchMode) {
      setBusy(true);
      try {
        const created = await queue.uploadOne(items[0]);
        await queryClient.invalidateQueries({ queryKey: queryKeys.analyses });
        navigate(`/analyses/${created.id}`);
      } catch (err) {
        setUploadError(errorMessage(err));
        setBusy(false);
      }
      return;
    }
    await runBatch(items);
  };

  const retry = (key: string) => {
    const item = items.find((it) => it.key === key);
    if (item) void runBatch([item]);
  };

  const failedCount = items.filter((it) => it.state === "failed").length;
  const single = items.length === 1 && !batchMode;
  const singleProgress = single && items[0].state === "uploading" ? Math.round(items[0].progress * 100) : null;
  const buttonLabel = single
    ? "Analyze"
    : batchMode && failedCount === items.length
      ? `Retry ${failedCount} failed`
      : `Analyze ${items.length} files`;

  return (
    <div className="space-y-14">
      <section className="mx-auto max-w-3xl">
        <div className="text-center">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Is this document genuine?</h1>
          <p className="mx-auto mt-3 max-w-xl text-base text-slate-600 dark:text-slate-400">
            Upload a screenshot, scan, photo, PDF or Word file. We look for traces of editing and forgery and show
            you exactly where.
          </p>
        </div>

        <div className="mt-8 space-y-4">
          <div>
            <Dropzone
              onFiles={onFiles}
              disabled={busy}
              invalid={rejected.length > 0}
              describedBy={rejected.length > 0 ? errorId : undefined}
            />
            <p className="mt-2 text-center text-xs text-slate-500 dark:text-slate-400">Each file is analysed separately.</p>
          </div>

          {rejected.length > 0 && (
            <div id={errorId} role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm dark:border-red-500/30 dark:bg-red-500/10">
              <div className="flex items-start justify-between gap-3">
                <p className="font-medium text-red-700 dark:text-red-300">
                  {rejected.length === 1 ? "1 file was not added" : `${rejected.length} files were not added`}
                </p>
                <button
                  type="button"
                  onClick={queue.clearRejected}
                  className="rounded text-xs font-medium text-red-700 hover:underline focus-ring dark:text-red-300"
                >
                  Dismiss
                </button>
              </div>
              <ul className="mt-1 space-y-0.5 text-red-700 dark:text-red-300">
                {rejected.map((r, i) => (
                  <li key={`${r.name}-${i}`} className="break-words">
                    <span className="font-medium">{r.name}</span>: {r.error}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {items.length > 0 && (
            <div className="card overflow-hidden">
              <SelectedFiles
                items={items}
                showErrors={batchMode}
                disabled={busy}
                onRemove={queue.remove}
                onRetry={retry}
              />
              <div className="flex flex-col gap-3 border-t border-slate-200 px-4 py-3 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-end">
                {batchMode && failedCount > 0 && failedCount < items.length && !busy && (
                  <button type="button" className="btn-secondary" onClick={() => void runBatch(items.filter((it) => it.state === "failed"))}>
                    <RotateCcw className="h-4 w-4" aria-hidden="true" />
                    Retry {failedCount} failed
                  </button>
                )}
                <button type="button" className="btn-primary sm:min-w-36" onClick={submit} disabled={busy}>
                  {busy ? (
                    <>
                      <Spinner className="h-4 w-4 text-white" label="Uploading" />
                      {singleProgress !== null ? (singleProgress < 100 ? `${singleProgress}%` : "Starting…") : "Uploading…"}
                    </>
                  ) : (
                    <>
                      {buttonLabel}
                      <ArrowRight className="h-4 w-4" aria-hidden="true" />
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {uploadError && (
            <ErrorAlert title="Upload failed" onDismiss={() => setUploadError(null)}>
              {uploadError}
            </ErrorAlert>
          )}

          {batch.ids.length > 0 && <BatchPanel ids={batch.ids} onClear={batch.clear} />}
        </div>
      </section>

      <section aria-labelledby="checks-heading">
        <h2 id="checks-heading" className="text-lg font-semibold">
          What we check
        </h2>
        <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CHECKS.map(({ title, body, Icon }) => (
            <li key={title} className="card p-5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </div>
              <h3 className="mt-3 text-sm font-semibold">{title}</h3>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{body}</p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="recent-heading">
        <div className="flex items-center justify-between">
          <h2 id="recent-heading" className="text-lg font-semibold">
            Recent analyses
          </h2>
          <Link to="/analyses" className="text-sm font-medium text-indigo-600 hover:underline focus-ring rounded dark:text-indigo-400">
            View all
          </Link>
        </div>
        <div className="mt-4">
          {recent.isPending ? (
            <div className="card flex justify-center p-8">
              <Spinner label="Loading recent analyses" />
            </div>
          ) : recent.isError ? (
            <ErrorAlert title="Couldn't load recent analyses">{errorMessage(recent.error)}</ErrorAlert>
          ) : recent.data.items.length === 0 ? (
            <p className="card p-6 text-center text-sm text-slate-500 dark:text-slate-400">
              Nothing analyzed yet. Your five most recent uploads will appear here.
            </p>
          ) : (
            <ul className="card divide-y divide-slate-100 overflow-hidden dark:divide-slate-800">
              {recent.data.items.slice(0, 5).map((a) => (
                <AnalysisRow key={a.id} analysis={a} />
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
