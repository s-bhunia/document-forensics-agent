import { CheckCircle2 } from "lucide-react";

export function ChecksPassed({ checks }: { checks: string[] }) {
  return (
    <section className="card p-5" aria-labelledby="checks-passed-heading">
      <h2 id="checks-passed-heading" className="text-base font-semibold">
        Checks passed <span className="font-normal text-slate-500">({checks.length})</span>
      </h2>
      {checks.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">No checks passed cleanly.</p>
      ) : (
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {checks.map((c) => (
            <li key={c} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" aria-hidden="true" />
              <span>{c}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
