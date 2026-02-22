import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { ErrorPage } from '@/pages/errors/ErrorPage';

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
        return { hasError: true, errorMsg: error.message };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("Uncaught error intercepted by GlobalErrorBoundary:", error, errorInfo);
    }

    public render() {
        if (this.state.hasError) {
            return <ErrorPage error={new Error(this.state.errorMsg)} />;
        }
        return this.props.children;
    }
}
