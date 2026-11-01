import { Link } from "react-router-dom";
import { FileImage, FileText, FileType2, Trash2 } from "lucide-react";
import type { AnalysisSummary } from "../api/types";
import { formatBytes, formatDateTime, formatRelative } from "../lib/format";
import { LabelBadge, StatusBadge } from "./Badges";

export function FileIcon({ contentType, className = "h-5 w-5" }: { contentType: string; className?: string }) {
  if (contentType.startsWith("image/")) return <FileImage className={className} aria-hidden="true" />;
  if (contentType === "application/pdf") return <FileText className={className} aria-hidden="true" />;
  return <FileType2 className={className} aria-hidden="true" />;
}

interface Props {
  analysis: AnalysisSummary;
  onDelete?: (analysis: AnalysisSummary) => void;
}

export function AnalysisRow({ analysis: a, onDelete }: Props) {
  return (
    <li className="group relative flex items-center gap-3 px-4 py-3 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40 sm:gap-4">
      <div className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 min-[400px]:flex">
        <FileIcon contentType={a.content_type} />
      </div>
      <div className="min-w-0 flex-1">
        <Link
          to={`/analyses/${a.id}`}
          className="block truncate text-sm font-medium after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:rounded-lg focus-visible:after:ring-2 focus-visible:after:ring-inset focus-visible:after:ring-indigo-500"
          title={a.filename}
        >
          {a.filename}
        </Link>
        <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">
          <time dateTime={a.created_at} title={formatDateTime(a.created_at)}>
            {formatRelative(a.created_at)}
          </time>
          {" · "}
          {formatBytes(a.size_bytes)}
          {a.status === "completed" && a.finding_count != null && (
            <>
              {" · "}
              {a.finding_count} finding{a.finding_count === 1 ? "" : "s"}
            </>
          )}
        </p>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1 sm:flex-row sm:items-center sm:gap-2">
        {a.status === "completed" && a.label ? (
          <LabelBadge label={a.label} riskScore={a.risk_score} />
        ) : (
          <StatusBadge status={a.status} />
        )}
      </div>
      {onDelete && (
        <button
          type="button"
          onClick={() => onDelete(a)}
          className="relative z-10 shrink-0 rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 dark:hover:bg-red-500/10 dark:hover:text-red-400"
          aria-label={`Delete ${a.filename}`}
          title="Delete"
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
    </li>
  );
}
