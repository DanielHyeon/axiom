import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { ErrorFallback } from '@/components/ErrorFallback';

interface Props {
 children?: ReactNode;
}

interface State {
 hasError: boolean;
 error: Error | null;
 componentStack: string | null;
}

/**
 * 에러 정보를 서버에 비동기로 전송한다 (navigator.sendBeacon 사용).
 */
function reportError(error: Error, componentStack?: string) {
  try {
    const payload = JSON.stringify({
      message: error.message,
      stack: error.stack?.slice(0, 1000),
      component_stack: componentStack?.slice(0, 500),
      url: window.location.href,
      timestamp: new Date().toISOString(),
      user_agent: navigator.userAgent,
    });
    navigator.sendBeacon('/api/v1/client-errors', payload);
  } catch {
    // beacon 전송 실패 시 무시
  }
}

/**
 * 페이지(또는 라우트) 단위 에러 경계. 자식에서 발생한 에러를 잡아 ErrorFallback 을 렌더한다.
 * MainLayout 의 Outlet 을 감싸 사용하면, 해당 페이지만 에러 UI 로 대체되고
 * Header/Sidebar 는 유지된다.
 */
export class PageErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    componentStack: null,
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('PageErrorBoundary:', error, errorInfo);
    // 서버에 에러 보고 (비차단)
    reportError(error, errorInfo.componentStack ?? undefined);
    this.setState({ componentStack: errorInfo.componentStack ?? null });
  }

  /** 에러 상태를 초기화하여 자식 트리를 다시 렌더링 */
  private handleRetry = () => {
    this.setState({ hasError: false, error: null, componentStack: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <ErrorFallback
          error={this.state.error}
          onRetry={this.handleRetry}
          isPageLevel
        />
      );
    }
    return this.props.children;
  }
}
