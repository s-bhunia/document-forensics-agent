import clsx from "clsx";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { LogoMark } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";
import { ErrorBoundary } from "./ErrorBoundary";

const navClass = ({ isActive }: { isActive: boolean }) =>
  clsx(
    "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500",
    isActive
      ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300"
      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white",
  );

export function Layout() {
  const location = useLocation();
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-3 focus:py-2 focus:shadow dark:focus:bg-slate-900"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-2 px-4 sm:gap-4 sm:px-6">
          <Link
            to="/"
            className="flex shrink-0 items-center gap-2 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <LogoMark className="h-7 w-7" />
            <span className="text-sm font-semibold tracking-tight sm:text-base">
              Doxket <span className="hidden text-slate-500 dark:text-slate-400 min-[440px]:inline">Forensics</span>
            </span>
          </Link>
          <nav aria-label="Main" className="ml-auto flex items-center gap-1 sm:ml-6 sm:mr-auto">
            <NavLink to="/" end className={navClass}>
              Analyze
            </NavLink>
            <NavLink to="/analyses" end className={navClass}>
              History
            </NavLink>
          </nav>
          <ThemeToggle />
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
        <ErrorBoundary key={location.pathname}>
          <Outlet />
        </ErrorBoundary>
      </main>
      <footer className="border-t border-slate-200 px-4 py-6 text-center text-xs text-slate-500 dark:border-slate-800">
        Automated forensic signals are indicators, not proof. Review findings before acting on them.
      </footer>
    </div>
  );
}
