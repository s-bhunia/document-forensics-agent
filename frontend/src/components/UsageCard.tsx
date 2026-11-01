import clsx from "clsx";
import { Coins } from "lucide-react";
import type { Usage } from "../api/types";
import { formatTokens, formatUsd } from "../lib/format";

export function UsageCard({ usage, className }: { usage: Usage; className?: string }) {
  const p = usage.prices_per_million;
  return (
    <section
      aria-labelledby="usage-heading"
      className={clsx("rounded-lg border border-slate-200 p-4 dark:border-slate-800", className)}
    >
      <h3 id="usage-heading" className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        <Coins className="h-3.5 w-3.5" aria-hidden="true" />
        Cost &amp; tokens
      </h3>
      <p className="mt-2 text-xl font-semibold tabular-nums" data-testid="usage-per-page">
        {formatUsd(usage.cost_per_page_usd)} <span className="text-sm font-normal text-slate-500">per page</span>
      </p>
      <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm min-[420px]:grid-cols-2">
        <Stat term="Total cost" value={formatUsd(usage.cost_usd)} testId="usage-total" />
        <Stat term="Calls" value={usage.calls.toLocaleString("en-US")} testId="usage-calls" />
        <Stat
          term="Input tokens"
          value={formatTokens(usage.input_tokens)}
          note={usage.cached_tokens > 0 ? `of which ${formatTokens(usage.cached_tokens)} cached` : undefined}
          testId="usage-input"
        />
        <Stat
          term="Output tokens"
          value={formatTokens(usage.output_tokens)}
          note={usage.thinking_tokens > 0 ? `incl. ${formatTokens(usage.thinking_tokens)} thinking` : undefined}
          testId="usage-output"
        />
      </dl>
      <p className="mt-3 text-xs text-slate-500 dark:text-slate-400" data-testid="usage-prices">
        {`Prices per 1M tokens: input $${p.input.toFixed(2)} · cached input $${p.cached_input.toFixed(2)} · output $${p.output.toFixed(2)}`}
      </p>
    </section>
  );
}

function Stat({ term, value, note, testId }: { term: string; value: string; note?: string; testId: string }) {
  return (
    <div data-testid={testId}>
      <dt className="text-xs text-slate-500 dark:text-slate-400">{term}</dt>
      <dd className="font-medium tabular-nums">
        {value}
        {note && <span className="ml-1.5 text-xs font-normal text-slate-500 dark:text-slate-400">{note}</span>}
      </dd>
    </div>
  );
}
