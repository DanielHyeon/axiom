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
 * beacon API 는 페이지 언로드 시에도 데이터를 안정적으로 전송할 수 있다.
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
    // beacon 전송 실패 시 무시 — 사용자 경험에 영향을 주지 않는다
  }
}

/**
 * 애플리케이션 최상위 에러 경계.
 * 자식 트리에서 발생한 렌더 에러를 잡아 사용자 친화적 UI 를 보여주고,
 * beacon API 로 오류를 서버에 자동 보고한다.
 */
export class GlobalErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    componentStack: null,
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error intercepted by GlobalErrorBoundary:', error, errorInfo);
    // 서버에 에러 보고 (비차단)
    reportError(error, errorInfo.componentStack ?? undefined);
    this.setState({ componentStack: errorInfo.componentStack ?? null });
  }

  /** 페이지 전체를 새로고침하여 다시 시도 */
  private handleRetry = () => {
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <ErrorFallback
          error={this.state.error}
          onRetry={this.handleRetry}
        />
      );
    }
    return this.props.children;
  }
}
