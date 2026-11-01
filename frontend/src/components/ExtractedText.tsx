import { useState } from "react";
import { Check, Copy } from "lucide-react";
import type { OcrPage } from "../api/types";

export function ExtractedText({ ocr }: { ocr: OcrPage[] }) {
  const pages = [...ocr].sort((a, b) => a.page - b.page).filter((p) => p.lines.length > 0);
  const [copied, setCopied] = useState(false);

  if (pages.length === 0) {
    return (
      <p className="card p-6 text-sm text-slate-500 dark:text-slate-400">No text was extracted from this document.</p>
    );
  }

  const copyAll = async () => {
    const text = pages.map((p) => `Page ${p.page}\n${p.lines.map((l) => l.text).join("\n")}`).join("\n\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button type="button" className="btn-secondary py-1.5" onClick={copyAll}>
          {copied ? <Check className="h-4 w-4" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
          {copied ? "Copied" : "Copy all text"}
        </button>
      </div>
      {pages.map((p) => (
        <section key={p.page} className="card overflow-hidden" aria-label={`Text on page ${p.page}`}>
          <h3 className="border-b border-slate-200 px-4 py-2 text-sm font-semibold dark:border-slate-800">
            Page {p.page}{" "}
            <span className="font-normal text-slate-500">
              · {p.lines.length} line{p.lines.length === 1 ? "" : "s"}
            </span>
          </h3>
          <ol className="max-h-96 overflow-auto px-4 py-3 font-mono text-xs leading-6">
            {p.lines.map((l, i) => (
              <li key={i} className="flex gap-3">
                <span className="w-8 shrink-0 select-none text-right text-slate-400">{i + 1}</span>
                <span className="min-w-0 whitespace-pre-wrap break-words text-slate-800 dark:text-slate-200">
                  {l.text}
                </span>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}
