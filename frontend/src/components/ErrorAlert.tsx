import clsx from "clsx";
import { AlertTriangle, X } from "lucide-react";
import type { ReactNode } from "react";

interface Props {
  title?: string;
  children: ReactNode;
  onDismiss?: () => void;
  action?: ReactNode;
  className?: string;
}

export function ErrorAlert({ title = "Something went wrong", children, onDismiss, action, className }: Props) {
  return (
    <div
      role="alert"
      className={clsx(
        "flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800",
        "dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200",
        className,
      )}
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{title}</p>
        <div className="mt-0.5 break-words text-red-700 dark:text-red-300">{children}</div>
        {action && <div className="mt-2">{action}</div>}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="rounded-md p-1 text-red-600 hover:bg-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 dark:text-red-300 dark:hover:bg-red-500/20"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "An unexpected error occurred.";
}
