import clsx from "clsx";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight, ImageOff, Layers } from "lucide-react";
import type { PageInfo } from "../api/types";
import { fileUrl } from "../api/client";
import type { NumberedFinding } from "../lib/findings";
import { SEVERITY_META } from "../lib/meta";

type LayerKey = "original" | "ela" | "noise";
type Zoom = "fit" | "100" | "200";

const LAYER_LABELS: Record<LayerKey, string> = { original: "Original", ela: "ELA", noise: "Noise" };
const ZOOM_LABELS: Record<Zoom, string> = { fit: "Fit", "100": "100%", "200": "200%" };

interface Props {
  analysisId: string;
  pages: PageInfo[];
  findings: NumberedFinding[];
  currentPage: number;
  onPageChange: (page: number) => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function PageViewer({ analysisId, pages, findings, currentPage, onPageChange, selectedId, onSelect }: Props) {
  const page = pages.find((p) => p.number === currentPage) ?? pages[0];
  const [layer, setLayer] = useState<LayerKey>("original");
  const [opacity, setOpacity] = useState(0.7);
  const [zoom, setZoom] = useState<Zoom>("fit");
  const [imageError, setImageError] = useState(false);
  const boxRefs = useRef(new Map<string, HTMLButtonElement>());

  const availableLayers = useMemo<LayerKey[]>(() => {
    if (!page) return ["original"];
    const keys: LayerKey[] = ["original"];
    if (page.layers?.ela) keys.push("ela");
    if (page.layers?.noise) keys.push("noise");
    return keys;
  }, [page]);

  useEffect(() => {
    if (!availableLayers.includes(layer)) setLayer("original");
  }, [availableLayers, layer]);

  useEffect(() => setImageError(false), [page?.image]);

  const pageFindings = useMemo(
    () => (page ? findings.filter((f) => f.page === page.number && f.box) : []),
    [findings, page],
  );

  const findingCountByPage = useMemo(() => {
    const m = new Map<number, number>();
    for (const f of findings) if (f.page != null && f.box) m.set(f.page, (m.get(f.page) ?? 0) + 1);
    return m;
  }, [findings]);

  useEffect(() => {
    if (!selectedId) return;
    const el = boxRefs.current.get(selectedId);
    el?.scrollIntoView?.({ behavior: "smooth", block: "center", inline: "center" });
  }, [selectedId, currentPage]);

  if (!page) {
    return (
      <div className="card flex flex-col items-center justify-center gap-2 p-10 text-sm text-slate-500">
        <ImageOff className="h-6 w-6" aria-hidden="true" />
        No page images are available for this document.
      </div>
    );
  }

  const layerPath = layer === "original" ? null : page.layers[layer];
  const innerStyle =
    zoom === "fit" ? { width: "100%" } : { width: page.width * (zoom === "200" ? 2 : 1), maxWidth: "none" };
  const pageIndex = pages.findIndex((p) => p.number === page.number);

  return (
    <section aria-label="Page viewer" className="card overflow-hidden">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-slate-200 px-3 py-2.5 dark:border-slate-800">
        {pages.length > 1 && (
          <div className="flex items-center gap-1" role="group" aria-label="Pages">
            <button
              type="button"
              className="btn-ghost px-2 py-1"
              aria-label="Previous page"
              disabled={pageIndex <= 0}
              onClick={() => onPageChange(pages[pageIndex - 1].number)}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            </button>
            <label className="sr-only" htmlFor="page-select">
              Page
            </label>
            <select
              id="page-select"
              value={page.number}
              onChange={(e) => onPageChange(Number(e.target.value))}
              className="input w-auto py-1 pr-8 text-sm"
            >
              {pages.map((p) => {
                const n = findingCountByPage.get(p.number) ?? 0;
                return (
                  <option key={p.number} value={p.number}>
                    Page {p.number} of {pages.length}
                    {n ? ` · ${n} marked` : ""}
                  </option>
                );
              })}
            </select>
            <button
              type="button"
              className="btn-ghost px-2 py-1"
              aria-label="Next page"
              disabled={pageIndex >= pages.length - 1}
              onClick={() => onPageChange(pages[pageIndex + 1].number)}
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        )}

        {availableLayers.length > 1 && (
          <Segmented
            label="Layer"
            icon={<Layers className="h-4 w-4 text-slate-400" aria-hidden="true" />}
            options={availableLayers}
            value={layer}
            onChange={setLayer}
            render={(k) => LAYER_LABELS[k]}
          />
        )}

        <Segmented
          label="Zoom"
          options={["fit", "100", "200"] as Zoom[]}
          value={zoom}
          onChange={setZoom}
          render={(z) => ZOOM_LABELS[z]}
          className="ml-auto"
        />
      </div>

      {layerPath && (
        <div className="flex items-center gap-3 border-b border-slate-200 px-3 py-2 text-xs dark:border-slate-800">
          <label htmlFor="layer-opacity" className="font-medium text-slate-600 dark:text-slate-400">
            {LAYER_LABELS[layer]} opacity
          </label>
          <input
            id="layer-opacity"
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={opacity}
            onChange={(e) => setOpacity(Number(e.target.value))}
            className="w-40 accent-indigo-600"
          />
          <span className="tabular-nums text-slate-500">{Math.round(opacity * 100)}%</span>
        </div>
      )}

      <div className="max-h-[75vh] overflow-auto bg-slate-100 p-3 dark:bg-slate-950/60 sm:p-4">
        <div className="relative mx-auto" style={innerStyle} data-testid="page-canvas">
          {imageError ? (
            <div
              className="flex items-center justify-center gap-2 bg-white text-sm text-slate-500 dark:bg-slate-900"
              style={{ aspectRatio: `${page.width} / ${page.height}` }}
            >
              <ImageOff className="h-5 w-5" aria-hidden="true" />
              Page image could not be loaded
            </div>
          ) : (
            <img
              src={fileUrl(analysisId, page.image)}
              alt={`Page ${page.number}`}
              width={page.width}
              height={page.height}
              onError={() => setImageError(true)}
              className="block h-auto w-full select-none bg-white shadow-sm"
              draggable={false}
            />
          )}
          {layerPath && (
            <img
              src={fileUrl(analysisId, layerPath)}
              alt={`${LAYER_LABELS[layer]} layer for page ${page.number}`}
              className="pointer-events-none absolute inset-0 h-full w-full select-none mix-blend-normal"
              style={{ opacity }}
              draggable={false}
            />
          )}
          {pageFindings.map((f) => {
            const [x, y, w, h] = f.box!;
            const meta = SEVERITY_META[f.severity];
            const selected = f.id === selectedId;
            return (
              <button
                key={f.id}
                type="button"
                ref={(el) => {
                  if (el) boxRefs.current.set(f.id, el);
                  else boxRefs.current.delete(f.id);
                }}
                data-testid={`box-${f.id}`}
                aria-label={`Finding ${f.number}: ${f.title}`}
                aria-pressed={selected}
                onClick={() => onSelect(f.id)}
                className={clsx(
                  "absolute rounded-[3px] border-2 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1",
                  selected && "z-10 animate-[pulse_1.5s_ease-in-out_2]",
                )}
                style={{
                  left: `${x * 100}%`,
                  top: `${y * 100}%`,
                  width: `${w * 100}%`,
                  height: `${h * 100}%`,
                  borderColor: meta.stroke,
                  backgroundColor: selected ? meta.fill.replace("0.14", "0.28") : meta.fill,
                  boxShadow: selected ? `0 0 0 3px ${meta.stroke}55, 0 0 0 9999px rgba(15,23,42,0.18)` : undefined,
                }}
              >
                <span
                  className="absolute -left-0.5 -top-0.5 flex h-5 min-w-5 -translate-y-full items-center justify-center rounded px-1 text-[11px] font-semibold leading-none text-white shadow"
                  style={{ backgroundColor: meta.stroke }}
                  aria-hidden="true"
                >
                  {f.number}
                </span>
              </button>
            );
          })}
        </div>
      </div>
      <p className="border-t border-slate-200 px-3 py-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
        {pageFindings.length === 0
          ? "No localized findings on this page."
          : `${pageFindings.length} marked region${pageFindings.length === 1 ? "" : "s"} on this page. Select a box to see details.`}
      </p>
    </section>
  );
}

interface SegmentedProps<T extends string> {
  label: string;
  options: T[];
  value: T;
  onChange: (v: T) => void;
  render: (v: T) => string;
  icon?: ReactNode;
  className?: string;
}

function Segmented<T extends string>({ label, options, value, onChange, render, icon, className }: SegmentedProps<T>) {
  return (
    <div className={clsx("flex items-center gap-2", className)}>
      {icon}
      <div
        role="radiogroup"
        aria-label={label}
        className="flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 dark:border-slate-700 dark:bg-slate-800/60"
      >
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            role="radio"
            aria-checked={opt === value}
            onClick={() => onChange(opt)}
            className={clsx(
              "rounded-md px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500",
              opt === value
                ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
                : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white",
            )}
          >
            {render(opt)}
          </button>
        ))}
      </div>
    </div>
  );
}
