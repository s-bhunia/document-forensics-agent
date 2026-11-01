import clsx from "clsx";
import { AlertCircle, RotateCcw, X } from "lucide-react";
import type { UploadItem } from "../hooks/useUploadQueue";
import { formatBytes } from "../lib/format";
import { FileIcon } from "./AnalysisRow";

interface Props {
  items: UploadItem[];
  showErrors: boolean;
  disabled: boolean;
  onRemove: (key: string) => void;
  onRetry: (key: string) => void;
}

export function SelectedFiles({ items, showErrors, disabled, onRemove, onRetry }: Props) {
  return (
    <ul className="divide-y divide-slate-100 dark:divide-slate-800" aria-label="Selected files">
      {items.map((it) => {
        const pct = Math.round(it.progress * 100);
        const failed = showErrors && it.state === "failed";
        return (
          <li key={it.key} className="flex items-center gap-3 px-4 py-3" data-testid="selected-file" data-state={it.state}>
            <div
              className={clsx(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                failed
                  ? "bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400"
                  : "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400",
              )}
            >
              {failed ? <AlertCircle className="h-5 w-5" aria-hidden="true" /> : <FileIcon contentType={it.file.type || ""} />}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium" title={it.file.name}>
                {it.file.name}
              </p>
              {failed ? (
                <p className="break-words text-xs text-red-600 dark:text-red-400">{it.error}</p>
              ) : (
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {formatBytes(it.file.size)}
                  {it.state === "uploading" && ` · ${pct < 100 ? `${pct}%` : "Starting…"}`}
                </p>
              )}
              {it.state === "uploading" && (
                <div
                  className="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"
                  role="progressbar"
                  aria-label={`Upload progress for ${it.file.name}`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={pct}
                >
                  <div className="h-full rounded-full bg-indigo-600 transition-[width] duration-200" style={{ width: `${pct}%` }} />
                </div>
              )}
            </div>
            {failed && (
              <button
                type="button"
                onClick={() => onRetry(it.key)}
                disabled={disabled}
                className="btn-secondary px-2.5 py-1 text-xs"
                aria-label={`Retry ${it.file.name}`}
              >
                <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                Retry
              </button>
            )}
            {it.state !== "uploading" && (
              <button
                type="button"
                onClick={() => onRemove(it.key)}
                disabled={disabled}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus-ring disabled:opacity-50 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                aria-label={`Remove ${it.file.name}`}
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
