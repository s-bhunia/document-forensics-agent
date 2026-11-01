import clsx from "clsx";
import { useEffect, useMemo, useRef, useState } from "react";
import { Crosshair, SearchX } from "lucide-react";
import type { Category, Severity } from "../api/types";
import {
  countBySeverity,
  filterFindings,
  presentCategories,
  sortBySeverity,
  type NumberedFinding,
} from "../lib/findings";
import { SEVERITY_META, SEVERITY_ORDER, categoryLabel } from "../lib/meta";
import { humanize } from "../lib/format";
import { META_EVIDENCE_KEYS, isUngrounded } from "../lib/investigation";
import { SeverityBadge } from "./Badges";

interface Props {
  findings: NumberedFinding[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onShowOnPage?: (id: string) => void;
}

export function FindingsList({ findings, selectedId, onSelect, onShowOnPage }: Props) {
  const [severities, setSeverities] = useState<Severity[]>([]);
  const [category, setCategory] = useState<Category | "all">("all");
  const cardRefs = useRef(new Map<string, HTMLElement>());

  const counts = useMemo(() => countBySeverity(findings), [findings]);
  const categories = useMemo(() => presentCategories(findings), [findings]);
  const visible = useMemo(
    () => sortBySeverity(filterFindings(findings, { severities, category })),
    [findings, severities, category],
  );

  useEffect(() => {
    if (!selectedId) return;
    cardRefs.current.get(selectedId)?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }, [selectedId]);

  const toggleSeverity = (s: Severity) =>
    setSeverities((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));

  const filtered = severities.length > 0 || category !== "all";

  return (
    <section aria-labelledby="findings-heading" className="flex min-w-0 flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="findings-heading" className="text-base font-semibold">
          Findings <span className="font-normal text-slate-500">({findings.length})</span>
        </h2>
        {categories.length > 1 && (
          <div>
            <label htmlFor="category-filter" className="sr-only">
              Filter by category
            </label>
            <select
              id="category-filter"
              value={category}
              onChange={(e) => setCategory(e.target.value as Category | "all")}
              className="input w-auto py-1 pr-8 text-sm"
            >
              <option value="all">All categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {categoryLabel(c)}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {findings.length > 0 && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by severity">
          {SEVERITY_ORDER.filter((s) => counts[s] > 0).map((s) => {
            const active = severities.includes(s);
            return (
              <button
                key={s}
                type="button"
                aria-pressed={active}
                onClick={() => toggleSeverity(s)}
                className={clsx(
                  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500",
                  active
                    ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:border-indigo-400 dark:bg-indigo-500/15 dark:text-indigo-200"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300",
                )}
              >
                <span className={clsx("h-2 w-2 rounded-full", SEVERITY_META[s].dot)} aria-hidden="true" />
                {SEVERITY_META[s].label}
                <span className="tabular-nums text-slate-400">{counts[s]}</span>
              </button>
            );
          })}
          {filtered && (
            <button
              type="button"
              className="rounded-full px-2 py-1 text-xs font-medium text-indigo-600 hover:underline focus-ring dark:text-indigo-400"
              onClick={() => {
                setSeverities([]);
                setCategory("all");
              }}
            >
              Clear filters
            </button>
          )}
        </div>
      )}

      {findings.length === 0 ? (
        <p className="card p-6 text-sm text-slate-600 dark:text-slate-400">
          No findings were raised for this document.
        </p>
      ) : visible.length === 0 ? (
        <div className="card flex flex-col items-center gap-2 p-6 text-sm text-slate-500">
          <SearchX className="h-5 w-5" aria-hidden="true" />
          No findings match the current filters.
        </div>
      ) : (
        <ol className="flex flex-col gap-3" aria-label="Findings list">
          {visible.map((f) => {
            const selected = f.id === selectedId;
            const evidence = Object.entries(f.evidence ?? {}).filter(([k]) => !META_EVIDENCE_KEYS.has(k));
            const ungrounded = isUngrounded(f.evidence);
            const locatable = f.page != null && f.box != null;
            return (
              <li
                key={f.id}
                ref={(el) => {
                  if (el) cardRefs.current.set(f.id, el);
                  else cardRefs.current.delete(f.id);
                }}
                data-testid={`finding-${f.id}`}
                data-selected={selected || undefined}
                className={clsx(
                  "card overflow-hidden border-l-4 transition-shadow",
                  selected && "ring-2 ring-indigo-500 dark:ring-indigo-400",
                )}
                style={{ borderLeftColor: SEVERITY_META[f.severity].stroke }}
              >
                <button
                  type="button"
                  onClick={() => onSelect(f.id)}
                  aria-pressed={selected}
                  className="flex w-full items-start gap-3 p-4 pb-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-500"
                >
                  <span
                    className="flex h-6 min-w-6 shrink-0 items-center justify-center rounded-md px-1 text-xs font-semibold text-white"
                    style={{ backgroundColor: SEVERITY_META[f.severity].stroke }}
                    aria-label={`Finding ${f.number}`}
                  >
                    {f.number}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={f.severity} />
                      <span className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                        {categoryLabel(f.category)}
                      </span>
                      {f.page != null && <span className="text-xs text-slate-400">· Page {f.page}</span>}
                      {ungrounded && (
                        <span className="rounded border border-dashed border-slate-300 px-1.5 py-0.5 text-[11px] font-medium text-slate-500 dark:border-slate-600 dark:text-slate-400">
                          Not verified by measurement
                        </span>
                      )}
                    </span>
                    <span className="mt-1.5 block font-medium leading-snug">{f.title}</span>
                  </span>
                </button>
                <div className="space-y-3 px-4 pb-4 pl-[3.25rem] text-sm">
                  <p className="text-slate-600 dark:text-slate-300">{f.detail}</p>
                  {f.text && (
                    <blockquote className="break-words rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-800 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-200">
                      “{f.text}”
                    </blockquote>
                  )}
                  {evidence.length > 0 && (
                    <table className="w-full text-xs">
                      <caption className="sr-only">Evidence for finding {f.number}</caption>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {evidence.map(([k, v]) => (
                          <tr key={k}>
                            <th scope="row" className="py-1 pr-3 text-left font-medium text-slate-500 dark:text-slate-400">
                              {humanize(k)}
                            </th>
                            <td className="break-all py-1 text-right font-mono tabular-nums text-slate-700 dark:text-slate-300">
                              {typeof v === "number" ? formatEvidenceNumber(v) : v}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {locatable && onShowOnPage && (
                    <button
                      type="button"
                      onClick={() => onShowOnPage(f.id)}
                      className="inline-flex items-center gap-1.5 rounded-md text-xs font-medium text-indigo-600 hover:text-indigo-500 focus-ring dark:text-indigo-400"
                    >
                      <Crosshair className="h-3.5 w-3.5" aria-hidden="true" />
                      Show on page
                    </button>
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

function formatEvidenceNumber(v: number): string {
  if (Number.isInteger(v)) return String(v);
  return Math.abs(v) < 1 ? v.toFixed(3) : v.toFixed(2);
}
