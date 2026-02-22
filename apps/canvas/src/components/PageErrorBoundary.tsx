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

/**
 * 페이지(또는 라우트) 단위 에러 경계. 자식에서 발생한 에러를 잡아 ErrorPage만 렌더한다.
 * MainLayout의 Outlet을 감싸 사용하면, 해당 페이지만 에러 UI로 대체되고
 * Header/Sidebar는 유지된다.
 */
export class PageErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    errorMsg: '',
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, errorMsg: error.message };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('PageErrorBoundary:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return <ErrorPage error={new Error(this.state.errorMsg)} />;
    }
    return this.props.children;
  }
}
