import type { Category, Label, Severity, Status } from "../api/types";

export const SEVERITY_ORDER: Severity[] = ["high", "medium", "low", "info"];

export const SEVERITY_META: Record<
  Severity,
  { label: string; chip: string; stroke: string; fill: string; dot: string }
> = {
  high: {
    label: "High",
    chip: "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-400/30",
    stroke: "#dc2626",
    fill: "rgba(220, 38, 38, 0.14)",
    dot: "bg-red-500",
  },
  medium: {
    label: "Medium",
    chip: "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-400/30",
    stroke: "#d97706",
    fill: "rgba(217, 119, 6, 0.14)",
    dot: "bg-amber-500",
  },
  low: {
    label: "Low",
    chip: "bg-sky-50 text-sky-700 ring-sky-600/20 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-400/30",
    stroke: "#0284c7",
    fill: "rgba(2, 132, 199, 0.14)",
    dot: "bg-sky-500",
  },
  info: {
    label: "Info",
    chip: "bg-slate-100 text-slate-700 ring-slate-500/20 dark:bg-slate-500/10 dark:text-slate-300 dark:ring-slate-400/30",
    stroke: "#64748b",
    fill: "rgba(100, 116, 139, 0.14)",
    dot: "bg-slate-400",
  },
};

export const LABEL_META: Record<Label, { label: string; chip: string; bar: string; text: string }> = {
  likely_authentic: {
    label: "Likely authentic",
    chip: "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-400/30",
    bar: "#10b981",
    text: "text-emerald-600 dark:text-emerald-400",
  },
  suspicious: {
    label: "Suspicious",
    chip: "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-400/30",
    bar: "#f59e0b",
    text: "text-amber-600 dark:text-amber-400",
  },
  highly_risky: {
    label: "Highly risky",
    chip: "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-400/30",
    bar: "#ef4444",
    text: "text-red-600 dark:text-red-400",
  },
};

export const STATUS_META: Record<Status, { label: string; chip: string }> = {
  queued: {
    label: "Queued",
    chip: "bg-slate-100 text-slate-700 ring-slate-500/20 dark:bg-slate-500/10 dark:text-slate-300 dark:ring-slate-400/30",
  },
  processing: {
    label: "Processing",
    chip: "bg-indigo-50 text-indigo-700 ring-indigo-600/20 dark:bg-indigo-500/10 dark:text-indigo-300 dark:ring-indigo-400/30",
  },
  completed: {
    label: "Completed",
    chip: "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-400/30",
  },
  failed: {
    label: "Failed",
    chip: "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-400/30",
  },
};

export const CATEGORY_LABELS: Record<Category, string> = {
  typography: "Typography",
  ink: "Ink",
  sharpness: "Sharpness",
  alignment: "Alignment",
  digits: "Digits",
  copy_move: "Copy-move",
  compression: "Compression",
  noise: "Noise",
  metadata: "Metadata",
  structure: "Structure",
  semantic: "Semantic",
};

export function categoryLabel(category: string): string {
  return (CATEGORY_LABELS as Record<string, string>)[category] ?? category.replace(/_/g, " ");
}

export function isActiveStatus(status: Status | undefined): boolean {
  return status === "queued" || status === "processing";
}
