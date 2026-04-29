// frontend/src/components/ErrorBoundary.tsx
import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props { children: ReactNode; }
interface State { hasError: boolean; }

export class ErrorBoundary extends Component<Props, State> {
  public state: State = { hasError: false };

  public static getDerivedStateFromError(_: Error): State {
    return { hasError: true };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-bg-0 text-text-100 p-6 text-center">
          <h2 className="text-2xl font-serif mb-4">Something went wrong</h2>
          <p className="text-text-400 mb-8 max-w-md">The application encountered an unexpected error. Please try reloading the page.</p>
          <button 
            onClick={() => window.location.reload()}
            className="px-6 py-2 bg-accent text-white rounded-xl hover:bg-accent-hover transition-colors"
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}