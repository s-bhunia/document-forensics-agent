import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertOctagon, RotateCcw } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled UI error", error, info.componentStack);
  }

  private reset = () => this.setState({ error: null });

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="mx-auto max-w-lg px-4 py-20 text-center" role="alert">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-600 dark:bg-red-500/10 dark:text-red-400">
          <AlertOctagon className="h-6 w-6" aria-hidden="true" />
        </div>
        <h1 className="mt-4 text-xl font-semibold">Something broke on this page</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{this.state.error.message}</p>
        <div className="mt-6 flex justify-center gap-3">
          <button type="button" onClick={this.reset} className="btn-primary">
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Try again
          </button>
          <a href="/" className="btn-secondary">
            Go to Analyze
          </a>
        </div>
      </div>
    );
  }
}
