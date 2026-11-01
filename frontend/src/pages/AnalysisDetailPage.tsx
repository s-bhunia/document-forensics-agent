import clsx from "clsx";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, RotateCcw, XCircle } from "lucide-react";
import { ApiError } from "../api/client";
import type { AnalysisDetail, AnalysisResult } from "../api/types";
import { useAnalysis } from "../hooks/useAnalyses";
import { numberFindings } from "../lib/findings";
import { isActiveStatus } from "../lib/meta";
import { ChecksPassed } from "../components/ChecksPassed";
import { ErrorAlert, errorMessage } from "../components/ErrorAlert";
import { ExtractedText } from "../components/ExtractedText";
import { InvestigationPanel } from "../components/InvestigationPanel";
import { FindingsList } from "../components/FindingsList";
import { PageViewer } from "../components/PageViewer";
import { ProcessingState } from "../components/ProcessingState";
import { ResultHeader } from "../components/ResultHeader";
import { PageLoader } from "../components/Spinner";
import { NotFoundPage } from "./NotFoundPage";

export function AnalysisDetailPage() {
  const { id = "" } = useParams<{ id: string }>();
  const query = useAnalysis(id);

  if (query.isPending) return <PageLoader label="Loading analysis" />;

  if (!query.data) {
    if (query.error instanceof ApiError && query.error.status === 404) {
      return (
        <NotFoundPage
          title="Analysis not found"
          message="This analysis doesn't exist or has been deleted."
        />
      );
    }
    return (
      <ErrorAlert
        title="Couldn't load this analysis"
        action={
          <button type="button" className="btn-secondary py-1" onClick={() => query.refetch()}>
            Retry
          </button>
        }
      >
        {errorMessage(query.error)}
      </ErrorAlert>
    );
  }

  const analysis = query.data;

  return (
    <div className="space-y-6">
      <BackLink />
      {query.isError && (
        <ErrorAlert title="Connection problem">
          Couldn't refresh this analysis: {errorMessage(query.error)}
        </ErrorAlert>
      )}
      {isActiveStatus(analysis.status) ? (
        <ProcessingState status={analysis.status} filename={analysis.filename} />
      ) : analysis.status === "failed" || !analysis.result ? (
        <FailedState analysis={analysis} />
      ) : (
        <CompletedView analysis={analysis} result={analysis.result} />
      )}
    </div>
  );
}

function BackLink() {
  return (
    <Link
      to="/analyses"
      className="inline-flex items-center gap-1.5 rounded text-sm font-medium text-slate-600 hover:text-slate-900 focus-ring dark:text-slate-400 dark:hover:text-white"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      History
    </Link>
  );
}

function FailedState({ analysis }: { analysis: AnalysisDetail }) {
  return (
    <div className="card mx-auto max-w-xl p-6 text-center sm:p-8" role="alert">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-600 dark:bg-red-500/10 dark:text-red-400">
        <XCircle className="h-6 w-6" aria-hidden="true" />
      </div>
      <h1 className="mt-4 text-lg font-semibold">Analysis failed</h1>
      <p className="mt-1 break-words text-sm text-slate-500 dark:text-slate-400">{analysis.filename}</p>
      <p className="mt-4 break-words rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-700 dark:bg-slate-800/60 dark:text-slate-300">
        {analysis.error || "The document could not be processed."}
      </p>
      <Link to="/" className="btn-primary mt-6">
        <RotateCcw className="h-4 w-4" aria-hidden="true" />
        Upload again
      </Link>
    </div>
  );
}

type Tab = "review" | "investigation" | "text";

function CompletedView({ analysis, result }: { analysis: AnalysisDetail; result: AnalysisResult }) {
  const findings = useMemo(() => numberFindings(result.findings), [result.findings]);
  const firstPage = result.pages[0]?.number ?? 1;
  const [currentPage, setCurrentPage] = useState(firstPage);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("review");
  const viewerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!result.pages.some((p) => p.number === currentPage)) setCurrentPage(firstPage);
  }, [result.pages, currentPage, firstPage]);

  const select = useCallback(
    (id: string) => {
      setSelectedId(id);
      const f = findings.find((x) => x.id === id);
      if (f?.page != null) setCurrentPage(f.page);
    },
    [findings],
  );

  const showOnPage = useCallback(
    (id: string) => {
      select(id);
      viewerRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    },
    [select],
  );

  const hasText = result.ocr.some((p) => p.lines.length > 0);
  const investigation = result.investigation ?? null;
  const tabs: { key: Tab; label: string }[] = [
    { key: "review", label: "Review" },
    ...(investigation ? [{ key: "investigation" as const, label: "Investigation" }] : []),
    { key: "text", label: `Extracted text${hasText ? "" : " (none)"}` },
  ];

  return (
    <>
      <ResultHeader analysis={analysis} result={result} />

      <div role="tablist" aria-label="Result sections" className="flex gap-1 border-b border-slate-200 dark:border-slate-800">
        {tabs.map((t) => (
          <button
            key={t.key}
            id={`tab-${t.key}`}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            aria-controls={`panel-${t.key}`}
            tabIndex={tab === t.key ? 0 : -1}
            onClick={() => setTab(t.key)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                const idx = tabs.findIndex((x) => x.key === tab);
                const step = e.key === "ArrowRight" ? 1 : -1;
                const next = tabs[(idx + step + tabs.length) % tabs.length].key;
                setTab(next);
                document.getElementById(`tab-${next}`)?.focus();
              }
            }}
            className={clsx(
              "-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-500",
              tab === t.key
                ? "border-indigo-600 text-indigo-700 dark:border-indigo-400 dark:text-indigo-300"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "investigation" && investigation ? (
        <div id="panel-investigation" role="tabpanel" aria-labelledby="tab-investigation">
          <InvestigationPanel investigation={investigation} />
        </div>
      ) : tab === "review" || tab === "investigation" ? (
        <div id="panel-review" role="tabpanel" aria-labelledby="tab-review" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <div ref={viewerRef} className="min-w-0 scroll-mt-20 lg:sticky lg:top-20 lg:self-start">
              <PageViewer
                analysisId={analysis.id}
                pages={result.pages}
                findings={findings}
                currentPage={currentPage}
                onPageChange={setCurrentPage}
                selectedId={selectedId}
                onSelect={select}
              />
            </div>
            <FindingsList findings={findings} selectedId={selectedId} onSelect={select} onShowOnPage={showOnPage} />
          </div>
          <ChecksPassed checks={result.checks_passed} />
        </div>
      ) : (
        <div id="panel-text" role="tabpanel" aria-labelledby="tab-text">
          <ExtractedText ocr={result.ocr} />
        </div>
      )}
    </>
  );
}
