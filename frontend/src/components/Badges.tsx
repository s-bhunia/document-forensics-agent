import clsx from "clsx";
import type { Label, Severity, Status } from "../api/types";
import { LABEL_META, SEVERITY_META, STATUS_META } from "../lib/meta";
import { formatPercent } from "../lib/format";

const base =
  "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset";

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const meta = SEVERITY_META[severity];
  return (
    <span className={clsx(base, meta.chip, className)} data-severity={severity}>
      <span className={clsx("h-1.5 w-1.5 rounded-full", meta.dot)} aria-hidden="true" />
      {meta.label}
    </span>
  );
}

export function LabelBadge({
  label,
  riskScore,
  className,
}: {
  label: Label;
  riskScore?: number | null;
  className?: string;
}) {
  const meta = LABEL_META[label];
  return (
    <span className={clsx(base, meta.chip, className)} data-label={label}>
      {meta.label}
      {riskScore != null && <span className="font-semibold tabular-nums">· {formatPercent(riskScore)}</span>}
    </span>
  );
}

export function StatusBadge({ status, className }: { status: Status; className?: string }) {
  const meta = STATUS_META[status];
  return (
    <span className={clsx(base, meta.chip, className)} data-status={status}>
      {status === "processing" && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-500" aria-hidden="true" />
      )}
      {meta.label}
    </span>
  );
}
