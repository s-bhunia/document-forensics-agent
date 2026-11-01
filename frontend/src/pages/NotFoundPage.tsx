import { Link } from "react-router-dom";
import { FileQuestion } from "lucide-react";

export function NotFoundPage({
  title = "Page not found",
  message = "The page you're looking for doesn't exist or has moved.",
}: {
  title?: string;
  message?: string;
}) {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
        <FileQuestion className="h-6 w-6" aria-hidden="true" />
      </div>
      <h1 className="mt-4 text-xl font-semibold">{title}</h1>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{message}</p>
      <div className="mt-6 flex justify-center gap-3">
        <Link to="/" className="btn-primary">
          Analyze a document
        </Link>
        <Link to="/analyses" className="btn-secondary">
          View history
        </Link>
      </div>
    </div>
  );
}
