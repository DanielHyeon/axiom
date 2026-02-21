import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface Props {
    children?: ReactNode;
}

interface State {
    hasError: boolean;
    errorMsg: string;
}

export class GlobalErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        errorMsg: ''
    };

    public static getDerivedStateFromError(error: Error): State {
        // Update state so the next render will show the fallback UI.
        return { hasError: true, errorMsg: error.message };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("Uncaught error intercepted by GlobalErrorBoundary:", error, errorInfo);
    }

    public render() {
        if (this.state.hasError) {
            return (
                <div className="flex flex-col items-center justify-center h-screen bg-gray-100 p-6">
                    <div className="bg-white p-8 rounded shadow-lg max-w-lg text-center border-t-8 border-red-600">
                        <h1 className="text-3xl font-bold text-gray-800 mb-4">Application Error</h1>
                        <p className="text-gray-600 mb-6 font-medium">
                            The Canvas interface encountered an unexpected structural fault.
                        </p>
                        <div className="bg-gray-100 text-red-700 p-4 rounded text-left text-sm mb-6 overflow-auto max-h-40">
                            <strong>Reason:</strong> {this.state.errorMsg}
                        </div>
                        <button
                            onClick={() => window.location.href = '/'}
                            className="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-6 rounded shadow"
                        >
                            Reload Application
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
