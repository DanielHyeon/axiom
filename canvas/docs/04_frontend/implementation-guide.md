# 프론트엔드 구현 가이드

<!-- affects: frontend -->
<!-- requires-update: 01_architecture/architecture-overview.md -->

## 이 문서가 답하는 질문

- 에러 처리는 어떤 패턴으로 구현하는가? (ErrorBoundary, API 에러, 토스트)
- 로딩 상태는 어떻게 표시하는가? (Suspense, 스켈레톤, 낙관적 업데이트)
- 폼은 어떻게 처리하는가? (React Hook Form + Zod 유효성 검증)
- 접근성(a11y)은 어떤 수준까지 구현하는가? (WCAG 2.1 AA)
- 테스트 전략은 무엇인가? (Vitest, React Testing Library, Playwright)
- 성능 최적화는 어떤 패턴을 따르는가? (메모이제이션, 가상화, 번들 분할)
- 국제화(i18n)는 어떻게 구현하는가? (react-i18next, ko/en)
- 실시간 통신은 어떤 패턴을 사용하는가? (WebSocket, SSE, Yjs)

---

## 1. 에러 처리 패턴

### 1.1 왜 이 패턴이 필요한가

사용자에게 의미 있는 에러 메시지를 전달하고, 에러 발생 시 애플리케이션이 완전히 중단되지 않도록 보호해야 한다. K-AIR에서는 에러 처리가 컴포넌트마다 제각각이었고, 전역 에러 처리가 없어 빈 화면이 표시되는 경우가 빈번했다.

### 1.2 에러 경계 (ErrorBoundary)

```typescript
// shared/components/ErrorFallback.tsx

import { Button } from '@/shared/ui/button';
import { AlertTriangle } from 'lucide-react';

interface ErrorFallbackProps {
  error: Error;
  resetErrorBoundary: () => void;
}

export function ErrorFallback({ error, resetErrorBoundary }: ErrorFallbackProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-4 p-8"
    >
      <AlertTriangle className="h-12 w-12 text-destructive" />
      <h2 className="text-lg font-semibold">문제가 발생했습니다</h2>
      <p className="text-sm text-muted-foreground max-w-md text-center">
        {error.message}
      </p>
      <Button onClick={resetErrorBoundary} variant="outline">
        다시 시도
      </Button>
    </div>
  );
}
```

```typescript
// 사용 예: 페이지 단위 ErrorBoundary 적용

import { ErrorBoundary } from 'react-error-boundary';
import { ErrorFallback } from '@/shared/components/ErrorFallback';

function CaseDetailPageWrapper() {
  return (
    <ErrorBoundary
      FallbackComponent={ErrorFallback}
      onReset={() => {
        // 에러 상태 초기화 (예: 캐시 무효화)
        queryClient.invalidateQueries({ queryKey: ['cases'] });
      }}
    >
      <CaseDetailPage />
    </ErrorBoundary>
  );
}
```

### 1.3 API 에러 처리

```typescript
// lib/api/errors.ts

/** Canvas 전역 에러 클래스 */
export class AppError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number,
    public readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = 'AppError';
  }

  /** 사용자에게 표시할 메시지 */
  get userMessage(): string {
    switch (this.status) {
      case 401: return '인증이 만료되었습니다. 다시 로그인해 주세요.';
      case 403: return '이 작업에 대한 권한이 없습니다.';
      case 404: return '요청한 리소스를 찾을 수 없습니다.';
      case 409: return '다른 사용자가 이미 수정했습니다. 새로고침 후 다시 시도해 주세요.';
      case 422: return '입력 데이터가 올바르지 않습니다.';
      case 429: return '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.';
      default:  return this.status >= 500
        ? '서버에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.'
        : this.message;
    }
  }
}
```

```typescript
// lib/api/createApiClient.ts (Axios 인터셉터)

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorResponse>) => {
    const status = error.response?.status ?? 0;
    const data = error.response?.data;

    // 401: 인증 만료 -> 로그인 리다이렉트
    if (status === 401) {
      useAuthStore.getState().logout();
      window.location.href = '/auth/login';
      return Promise.reject(error);
    }

    // AppError로 변환하여 일관된 에러 처리
    const appError = new AppError(
      data?.message ?? error.message,
      data?.code ?? 'UNKNOWN_ERROR',
      status,
      data?.details,
    );

    return Promise.reject(appError);
  },
);
```

### 1.4 TanStack Query 전역 에러 핸들러

```typescript
// app/queryClient.ts

import { QueryClient } from '@tanstack/react-query';
import { toast } from '@/shared/ui/toast';
import { AppError } from '@/lib/api/errors';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // 4xx 에러는 재시도하지 않음
        if (error instanceof AppError && error.status >= 400 && error.status < 500) {
          return false;
        }
        return failureCount < 3;
      },
      staleTime: 30_000,  // 30초
    },
    mutations: {
      onError: (error) => {
        // Mutation 에러는 토스트로 표시
        const message = error instanceof AppError
          ? error.userMessage
          : '알 수 없는 오류가 발생했습니다.';
        toast.error(message);
      },
    },
  },
});
```

### 1.5 에러 처리 규칙

#### 필수 (Required)

- 모든 페이지 컴포넌트는 `ErrorBoundary`로 감싸야 한다
- API 에러는 반드시 `AppError` 클래스를 통해 처리한다
- 401 응답은 전역 인터셉터에서 자동 처리 (개별 컴포넌트 처리 금지)
- 사용자에게 표시하는 에러 메시지는 한국어로 작성한다

#### 금지됨 (Forbidden)

- `try/catch`에서 에러를 삼키는 것 (`catch(e) {}` 빈 블록)
- 콘솔에만 에러를 출력하고 사용자에게 알리지 않는 것
- 에러 메시지에 스택 트레이스나 내부 구현 정보 노출

### 1.6 K-AIR 전환 노트

| K-AIR | Canvas | 변경 사유 |
|-------|--------|-----------|
| Vue `errorCaptured` hook | react-error-boundary | React 생태계 표준, 함수형 컴포넌트 지원 |
| Axios 에러 직접 처리 (컴포넌트마다 다름) | `AppError` 클래스 + 전역 인터셉터 | 일관된 에러 메시지, 중복 코드 제거 |
| `ElMessage.error()` (Element Plus) | Shadcn/ui `toast.error()` | 디자인 시스템 통일 |

---

## 2. 로딩 상태 패턴

### 2.1 왜 이 패턴이 필요한가

네트워크 요청 중 빈 화면 대신 의미 있는 피드백을 제공하여 체감 성능을 높인다. CLS(Cumulative Layout Shift)를 방지하기 위해 스켈레톤 UI가 실제 콘텐츠와 동일한 레이아웃을 유지해야 한다.

### 2.2 Suspense + 스켈레톤

```typescript
// 라우트 수준: SuspenseWrapper가 자동 적용 (router.tsx)
// 컴포넌트 수준: 직접 Suspense 사용

import { Suspense } from 'react';
import { Skeleton } from '@/shared/ui/skeleton';

// 스켈레톤은 실제 콘텐츠 레이아웃과 동일한 구조를 가진다
function CaseTableSkeleton() {
  return (
    <div className="space-y-3">
      {/* 테이블 헤더 */}
      <div className="flex gap-4 px-4">
        <Skeleton className="h-4 w-[200px]" />
        <Skeleton className="h-4 w-[120px]" />
        <Skeleton className="h-4 w-[80px]" />
        <Skeleton className="h-4 w-[150px]" />
      </div>
      {/* 테이블 행 5개 */}
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex gap-4 px-4 py-2">
          <Skeleton className="h-4 w-[200px]" />
          <Skeleton className="h-4 w-[120px]" />
          <Skeleton className="h-4 w-[80px]" />
          <Skeleton className="h-4 w-[150px]" />
        </div>
      ))}
    </div>
  );
}

// 사용
function CaseListSection() {
  return (
    <Suspense fallback={<CaseTableSkeleton />}>
      <CaseTable />
    </Suspense>
  );
}
```

### 2.3 TanStack Query 로딩 상태

```typescript
// hooks/useCases.ts

import { useSuspenseQuery } from '@tanstack/react-query';
import { caseApi } from '../api/caseApi';

export function useCases(filters: CaseFilters) {
  // useSuspenseQuery: Suspense와 통합, isLoading 불필요
  return useSuspenseQuery({
    queryKey: ['cases', filters],
    queryFn: () => caseApi.list(filters),
    staleTime: 30_000,
  });
}
```

### 2.4 낙관적 업데이트 (Optimistic Update)

```typescript
// hooks/useCaseMutation.ts

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { caseApi } from '../api/caseApi';
import { toast } from '@/shared/ui/toast';

export function useUpdateCaseStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: caseApi.updateStatus,

    // 서버 응답 전에 UI를 먼저 업데이트
    onMutate: async (variables) => {
      // 진행 중인 쿼리 취소 (덮어쓰기 방지)
      await queryClient.cancelQueries({ queryKey: ['cases'] });

      // 이전 데이터 스냅샷
      const previousCases = queryClient.getQueryData(['cases']);

      // 캐시를 낙관적으로 업데이트
      queryClient.setQueryData(['cases'], (old: Case[]) =>
        old.map((c) =>
          c.id === variables.caseId
            ? { ...c, status: variables.newStatus }
            : c,
        ),
      );

      return { previousCases };
    },

    // 에러 시 롤백
    onError: (_error, _variables, context) => {
      if (context?.previousCases) {
        queryClient.setQueryData(['cases'], context.previousCases);
      }
      toast.error('상태 변경에 실패했습니다.');
    },

    // 성공/실패 무관하게 서버 데이터로 동기화
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['cases'] });
    },
  });
}
```

### 2.5 로딩 상태 규칙

#### 필수 (Required)

- 스켈레톤 UI는 실제 콘텐츠와 동일한 높이/너비를 유지하여 CLS를 방지한다
- 데이터 Fetch는 `useSuspenseQuery`를 우선 사용한다 (Suspense 통합)
- 삭제/상태변경 등 빈번한 Mutation에는 낙관적 업데이트를 적용한다

#### 금지됨 (Forbidden)

- 전체 페이지를 커버하는 스피너 (로딩 영역을 최소화해야 함)
- `isLoading` 분기로 `null` 반환 (`Suspense`가 대체)
- 낙관적 업데이트 시 `onError` 롤백 누락

---

## 3. 폼 처리 패턴

### 3.1 왜 이 패턴이 필요한가

Canvas의 폼은 케이스 생성, 알림 규칙 편집, 데이터소스 연결, 이벤트 로그 바인딩 등 다양하다. 일관된 유효성 검증과 에러 표시를 위해 React Hook Form + Zod 조합을 표준으로 사용한다.

### 3.2 기본 폼 패턴

```typescript
// features/case-dashboard/components/CaseCreateForm.tsx

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/shared/ui/button';
import { Input } from '@/shared/ui/input';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/shared/ui/form';

// 1. Zod 스키마 정의 (유효성 규칙 + 타입 추론 동시 해결)
const caseCreateSchema = z.object({
  title: z
    .string()
    .min(1, '제목을 입력해 주세요.')
    .max(200, '제목은 200자 이내로 입력해 주세요.'),
  description: z
    .string()
    .max(2000, '설명은 2000자 이내로 입력해 주세요.')
    .optional(),
  priority: z.enum(['low', 'medium', 'high', 'critical'], {
    required_error: '우선순위를 선택해 주세요.',
  }),
  assigneeId: z.string().uuid('올바른 담당자를 선택해 주세요.').optional(),
});

// Zod 스키마에서 TypeScript 타입 자동 추론
type CaseCreateInput = z.infer<typeof caseCreateSchema>;

// 2. 폼 컴포넌트
export function CaseCreateForm({ onSubmit }: { onSubmit: (data: CaseCreateInput) => void }) {
  const form = useForm<CaseCreateInput>({
    resolver: zodResolver(caseCreateSchema),
    defaultValues: {
      title: '',
      description: '',
      priority: 'medium',
    },
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>제목</FormLabel>
              <FormControl>
                <Input placeholder="케이스 제목" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="priority"
          render={({ field }) => (
            <FormItem>
              <FormLabel>우선순위</FormLabel>
              <FormControl>
                <Select onValueChange={field.onChange} defaultValue={field.value}>
                  <SelectTrigger>
                    <SelectValue placeholder="선택" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">낮음</SelectItem>
                    <SelectItem value="medium">보통</SelectItem>
                    <SelectItem value="high">높음</SelectItem>
                    <SelectItem value="critical">긴급</SelectItem>
                  </SelectContent>
                </Select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? '생성 중...' : '케이스 생성'}
        </Button>
      </form>
    </Form>
  );
}
```

### 3.3 서버 에러와 폼 에러 연동

```typescript
// API 422 응답의 필드별 에러를 폼에 매핑

const mutation = useCreateCase();

async function handleSubmit(data: CaseCreateInput) {
  try {
    await mutation.mutateAsync(data);
    toast.success('케이스가 생성되었습니다.');
  } catch (error) {
    if (error instanceof AppError && error.status === 422 && error.details?.fields) {
      // 서버 유효성 에러를 폼 필드에 매핑
      const fields = error.details.fields as Record<string, string>;
      Object.entries(fields).forEach(([fieldName, message]) => {
        form.setError(fieldName as keyof CaseCreateInput, {
          type: 'server',
          message,
        });
      });
    }
  }
}
```

### 3.4 폼 처리 규칙

#### 필수 (Required)

- 유효성 검증 스키마는 `Zod`로 정의하고, 타입은 `z.infer`로 추론한다
- 서버 422 응답의 필드 에러는 `form.setError`로 폼에 반영한다
- 제출 중 상태(`isSubmitting`)에서 버튼을 비활성화한다
- 에러 메시지는 한국어로 작성한다

#### 금지됨 (Forbidden)

- `useState`로 폼 상태 직접 관리 (React Hook Form 사용)
- 유효성 검증 로직을 컴포넌트 내에 인라인으로 작성 (Zod 스키마 분리)
- `alert()`로 폼 에러 표시 (FormMessage 컴포넌트 사용)

---

## 4. 접근성 구현 가이드

### 4.1 왜 이 패턴이 필요한가

Canvas는 WCAG 2.1 AA 준수를 목표로 한다. 공공기관 및 대기업 고객의 접근성 요구사항을 충족하고, 키보드만으로 모든 핵심 기능을 사용할 수 있도록 보장한다. Shadcn/ui는 Radix UI 기반으로 대부분의 ARIA 패턴을 내장하고 있어 좋은 출발점이 된다.

### 4.2 시맨틱 HTML과 랜드마크

```typescript
// layouts/DashboardLayout.tsx

export function DashboardLayout() {
  return (
    <div className="flex h-screen">
      {/* 네비게이션 랜드마크 */}
      <nav aria-label="메인 네비게이션">
        <Sidebar />
      </nav>

      <div className="flex flex-1 flex-col">
        {/* 배너 랜드마크 */}
        <header>
          <Header />
        </header>

        {/* 메인 콘텐츠 랜드마크 */}
        <main id="main-content" className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

### 4.3 키보드 네비게이션

```typescript
// shared/hooks/useKeyboardShortcut.ts

import { useEffect } from 'react';

interface ShortcutConfig {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  handler: () => void;
  /** true이면 input/textarea에서도 동작 */
  enableInInput?: boolean;
}

export function useKeyboardShortcut(shortcuts: ShortcutConfig[]) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      // input, textarea, contentEditable에서는 기본적으로 무시
      const target = event.target as HTMLElement;
      const isInput = target.tagName === 'INPUT'
        || target.tagName === 'TEXTAREA'
        || target.isContentEditable;

      for (const shortcut of shortcuts) {
        if (isInput && !shortcut.enableInInput) continue;

        const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase();
        const ctrlMatch = !!shortcut.ctrl === (event.ctrlKey || event.metaKey);
        const shiftMatch = !!shortcut.shift === event.shiftKey;
        const altMatch = !!shortcut.alt === event.altKey;

        if (keyMatch && ctrlMatch && shiftMatch && altMatch) {
          event.preventDefault();
          shortcut.handler();
          return;
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);
}
```

### 4.4 ARIA 패턴

```typescript
// 데이터 테이블: 정렬 가능 헤더

<th
  role="columnheader"
  aria-sort={sortDirection === 'asc' ? 'ascending' : sortDirection === 'desc' ? 'descending' : 'none'}
  tabIndex={0}
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleSort(column);
    }
  }}
  onClick={() => toggleSort(column)}
>
  {column.label}
  <span className="sr-only">
    {sortDirection === 'asc' ? ', 오름차순 정렬됨' : sortDirection === 'desc' ? ', 내림차순 정렬됨' : ''}
  </span>
</th>
```

```typescript
// 토스트 알림: 스크린 리더를 위한 실시간 영역

<div
  role="status"
  aria-live="polite"       // 정보성 메시지
  aria-atomic="true"
  className="sr-only"
>
  {latestToastMessage}
</div>

<div
  role="alert"
  aria-live="assertive"    // 에러/긴급 메시지
  aria-atomic="true"
  className="sr-only"
>
  {latestErrorMessage}
</div>
```

### 4.5 색상 대비

```
최소 대비 비율 (WCAG 2.1 AA):
- 일반 텍스트 (< 18px):    4.5:1
- 큰 텍스트 (>= 18px bold): 3:1
- UI 컴포넌트/그래픽:       3:1

Canvas 디자인 토큰 검증:
- --foreground on --background:  OK (15.4:1)
- --primary on --background:     OK (4.6:1)
- --destructive on --background: OK (4.8:1)
- --muted-foreground on --background: OK (4.7:1)

도구: 색상 대비 검증은 axe DevTools 또는 Lighthouse를 사용한다.
```

### 4.6 접근성 규칙

#### 필수 (Required)

- 모든 이미지에 `alt` 텍스트 (장식 이미지는 `alt=""` + `aria-hidden="true"`)
- 모든 폼 요소에 연결된 `<label>` (Shadcn/ui FormLabel 사용)
- 포커스 표시(focus ring)를 제거하지 않는다 (`outline-none` 단독 사용 금지)
- 모달/다이얼로그는 포커스 트랩을 구현한다 (Radix Dialog가 자동 처리)
- 페이지 제목(`<title>`)은 라우트마다 변경한다

#### 금지됨 (Forbidden)

- `div`에 `onClick`만 추가하고 `role="button"`, `tabIndex`, `onKeyDown` 누락
- `color`만으로 상태를 구분 (아이콘/텍스트 보조 필수)
- `tabIndex` 양수값 사용 (`0` 또는 `-1`만 허용)
- `aria-label`과 시각적 텍스트가 불일치하는 것

---

## 5. 테스트 전략

### 5.1 왜 이 패턴이 필요한가

Canvas는 8+1개 Feature 모듈로 구성되며, 각 모듈은 독립적으로 개발/배포될 수 있다. 테스트 피라미드를 적용하여 단위 테스트로 빠른 피드백을 확보하고, 통합 테스트로 컴포넌트 동작을 검증하며, E2E 테스트로 핵심 사용자 시나리오를 보호한다.

### 5.2 테스트 피라미드

```
           /\
          /  \         E2E (Playwright)
         / 10 \        - 핵심 사용자 시나리오 10~15개
        /______\       - 로그인 -> 케이스 생성 -> 문서 편집 -> 승인
       /        \
      /   30     \     통합 테스트 (React Testing Library)
     /____________\    - 컴포넌트 + Hook + API Mock
    /              \   - 사용자 관점: 클릭, 입력, 결과 확인
   /      60        \
  /__________________\ 단위 테스트 (Vitest)
                       - 유틸, 스토어, 커스텀 Hook, Zod 스키마
                       - 순수 함수 위주
```

### 5.3 단위 테스트 (Vitest)

```typescript
// shared/utils/__tests__/format.test.ts

import { describe, it, expect } from 'vitest';
import { formatCurrency, formatDate, formatDuration } from '../format';

describe('formatCurrency', () => {
  it('한국 원화를 천 단위 쉼표로 포맷한다', () => {
    expect(formatCurrency(1234567, 'KRW')).toBe('1,234,567원');
  });

  it('0은 "0원"으로 표시한다', () => {
    expect(formatCurrency(0, 'KRW')).toBe('0원');
  });

  it('음수는 마이너스 기호를 포함한다', () => {
    expect(formatCurrency(-5000, 'KRW')).toBe('-5,000원');
  });
});

describe('formatDuration', () => {
  it('분 단위를 사람이 읽기 쉬운 형태로 변환한다', () => {
    expect(formatDuration(125)).toBe('2시간 5분');
    expect(formatDuration(60)).toBe('1시간');
    expect(formatDuration(45)).toBe('45분');
  });
});
```

### 5.4 통합 테스트 (React Testing Library)

```typescript
// features/case-dashboard/components/__tests__/CaseTable.test.tsx

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { CaseTable } from '../CaseTable';
import { QueryClientProvider } from '@tanstack/react-query';
import { createTestQueryClient } from '@/tests/utils/createTestQueryClient';
import { mockCases } from '@/tests/fixtures/cases';

// API Mock (MSW 또는 직접 Mock)
vi.mock('../../api/caseApi', () => ({
  caseApi: {
    list: vi.fn().mockResolvedValue({ data: mockCases, total: 3 }),
  },
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>,
  );
}

describe('CaseTable', () => {
  it('케이스 목록을 테이블로 표시한다', async () => {
    renderWithProviders(<CaseTable />);

    // 데이터가 로딩된 후 첫 번째 케이스가 표시되는지 확인
    expect(await screen.findByText('입고 검수 지연 건')).toBeInTheDocument();
    expect(screen.getByText('출고 오류 건')).toBeInTheDocument();
  });

  it('행을 클릭하면 상세 페이지로 이동한다', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CaseTable />);

    const row = await screen.findByText('입고 검수 지연 건');
    await user.click(row.closest('tr')!);

    // navigate가 호출되었는지 확인 (react-router mock 필요)
    expect(mockNavigate).toHaveBeenCalledWith('/cases/case-001');
  });

  it('상태 필터를 변경하면 목록이 갱신된다', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CaseTable />);

    const filterButton = await screen.findByRole('combobox', { name: '상태 필터' });
    await user.click(filterButton);
    await user.click(screen.getByRole('option', { name: '진행 중' }));

    // 필터링된 결과가 표시되는지 확인
    expect(await screen.findByText('입고 검수 지연 건')).toBeInTheDocument();
  });
});
```

### 5.5 E2E 테스트 (Playwright)

```typescript
// tests/e2e/case-workflow.spec.ts

import { test, expect } from '@playwright/test';

test.describe('케이스 워크플로우', () => {
  test.beforeEach(async ({ page }) => {
    // 로그인
    await page.goto('/auth/login');
    await page.getByLabel('이메일').fill('test@axiom.com');
    await page.getByLabel('비밀번호').fill('testpassword');
    await page.getByRole('button', { name: '로그인' }).click();
    await page.waitForURL('/dashboard');
  });

  test('케이스를 생성하고 문서를 첨부한다', async ({ page }) => {
    // 케이스 목록으로 이동
    await page.getByRole('link', { name: '케이스' }).click();
    await expect(page).toHaveURL('/cases');

    // 새 케이스 생성
    await page.getByRole('button', { name: '새 케이스' }).click();
    await page.getByLabel('제목').fill('E2E 테스트 케이스');
    await page.getByLabel('우선순위').selectOption('high');
    await page.getByRole('button', { name: '케이스 생성' }).click();

    // 생성 확인
    await expect(page.getByText('케이스가 생성되었습니다')).toBeVisible();

    // 문서 탭으로 이동
    await page.getByRole('tab', { name: '문서' }).click();
    await expect(page.getByText('문서가 없습니다')).toBeVisible();
  });
});
```

### 5.6 테스트 규칙

#### 필수 (Required)

- 모든 유틸 함수와 Zod 스키마에 단위 테스트 작성
- 사용자 상호작용이 있는 컴포넌트에 통합 테스트 작성
- 핵심 비즈니스 시나리오(로그인, 케이스 CRUD, 문서 승인)에 E2E 테스트 작성
- 테스트는 구현이 아닌 사용자 행동을 검증한다 (`getByRole`, `getByText` 우선)

#### 금지됨 (Forbidden)

- 테스트 ID(`data-testid`)를 첫 번째 선택자로 사용 (접근성 역할/텍스트 우선)
- 내부 상태(state)나 DOM 구조를 직접 검증 (사용자가 보는 결과 검증)
- `sleep`/`waitFor` 임의 대기 (Playwright의 `expect` 자동 대기 활용)
- 단위 테스트에서 네트워크 요청 발생 (모든 API는 Mock)

---

## 6. 성능 최적화 패턴

### 6.1 왜 이 패턴이 필요한가

Canvas는 데이터 집약적 애플리케이션이다. OLAP 피벗 테이블은 수천 행, 프로세스 디자이너는 수백 개 노드, Watch 대시보드는 실시간 이벤트를 처리한다. Core Web Vitals(LCP < 2.5s, INP < 200ms, CLS < 0.1)를 목표로 한다.

### 6.2 메모이제이션

```typescript
// 비용이 큰 계산 결과 캐싱
import { useMemo, useCallback } from 'react';

function PivotTable({ data, dimensions, measures }: PivotTableProps) {
  // useMemo: 피벗 계산은 비용이 크므로 입력이 변경될 때만 재계산
  const pivotResult = useMemo(
    () => computePivot(data, dimensions, measures),
    [data, dimensions, measures],
  );

  // useCallback: 자식 컴포넌트에 전달하는 핸들러 안정화
  const handleCellClick = useCallback(
    (rowKey: string, colKey: string) => {
      drillDown(rowKey, colKey);
    },
    [drillDown],
  );

  return <PivotGrid data={pivotResult} onCellClick={handleCellClick} />;
}

// React.memo: props가 변경되지 않으면 리렌더링 스킵
const PivotGrid = React.memo(function PivotGrid({
  data,
  onCellClick,
}: PivotGridProps) {
  // ...렌더링 로직
});
```

### 6.3 리스트 가상화

```typescript
// 수천 행의 테이블을 효율적으로 렌더링
import { useVirtualizer } from '@tanstack/react-virtual';

function VirtualizedTable({ rows }: { rows: DataRow[] }) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40,          // 각 행의 예상 높이 (px)
    overscan: 10,                     // 뷰포트 밖에 미리 렌더링할 행 수
  });

  return (
    <div ref={parentRef} className="h-[600px] overflow-auto">
      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
        {virtualizer.getVirtualItems().map((virtualRow) => (
          <div
            key={virtualRow.key}
            style={{
              position: 'absolute',
              top: virtualRow.start,
              height: virtualRow.size,
              width: '100%',
            }}
          >
            <TableRow data={rows[virtualRow.index]} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 6.4 번들 분할

```typescript
// vite.config.ts - 수동 청크 분할

export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // 벤더 라이브러리 분리
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-query': ['@tanstack/react-query'],
          'vendor-konva': ['react-konva', 'konva'],
          'vendor-yjs': ['yjs', 'y-websocket', 'y-indexeddb'],
          'vendor-charts': ['recharts'],
          // 라우트별 코드 분할은 React.lazy()가 자동 처리
        },
      },
    },
  },
});
```

```
번들 크기 예산:
- 초기 로드 (vendor + app shell): < 200KB (gzip)
- 라우트 청크 (각 페이지):         < 80KB (gzip)
- 이미지 에셋:                     WebP/AVIF, < 100KB per image
```

### 6.5 이미지 최적화

```typescript
// 반응형 이미지 컴포넌트

function OptimizedImage({ src, alt, ...props }: OptimizedImageProps) {
  return (
    <picture>
      <source srcSet={`${src}.avif`} type="image/avif" />
      <source srcSet={`${src}.webp`} type="image/webp" />
      <img
        src={`${src}.png`}
        alt={alt}
        loading="lazy"              // 뷰포트 밖 이미지 지연 로딩
        decoding="async"            // 디코딩을 메인 스레드에서 분리
        {...props}
      />
    </picture>
  );
}
```

### 6.6 성능 최적화 규칙

#### 필수 (Required)

- 100행 이상의 리스트/테이블은 `@tanstack/react-virtual`로 가상화한다
- 라우트 페이지는 `React.lazy()`로 코드 분할한다
- `useMemo`/`useCallback`은 측정 후 필요한 곳에만 적용한다 (premature optimization 방지)
- 번들 크기는 `vite-bundle-visualizer`로 정기 점검한다

#### 금지됨 (Forbidden)

- 모든 컴포넌트에 `React.memo` 무조건 적용 (성능 측정 근거 필요)
- `useMemo`/`useCallback` 의존성 배열에 `[]` (빈 배열)을 넣고 클로저 문제를 무시하는 것
- 번들 분석 없이 대형 라이브러리 추가 (moment.js, lodash 전체 import 등)

---

## 7. 국제화(i18n) 패턴

### 7.1 왜 이 패턴이 필요한가

Canvas는 한국어(ko)를 기본 언어로, 영어(en)를 보조 언어로 지원한다. K-AIR에서는 하드코딩된 한국어 문자열이 다수 존재하여 영어 지원이 불가능했다. react-i18next를 사용하여 모든 사용자 대면 문자열을 외부화한다.

### 7.2 설정

```typescript
// lib/i18n/i18n.ts

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import ko from './ko.json';
import en from './en.json';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      ko: { translation: ko },
      en: { translation: en },
    },
    fallbackLng: 'ko',               // 기본 한국어
    interpolation: {
      escapeValue: false,             // React가 XSS 방지
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
  });

export default i18n;
```

### 7.3 번역 파일 구조

```json
// lib/i18n/ko.json

{
  "common": {
    "save": "저장",
    "cancel": "취소",
    "delete": "삭제",
    "confirm": "확인",
    "search": "검색",
    "loading": "불러오는 중...",
    "noData": "데이터가 없습니다.",
    "error": "오류가 발생했습니다."
  },
  "cases": {
    "title": "케이스 관리",
    "create": "새 케이스",
    "detail": "케이스 상세",
    "status": {
      "draft": "초안",
      "filed": "접수",
      "in_progress": "진행 중",
      "review": "검토 중",
      "approved": "승인",
      "rejected": "반려",
      "closed": "종료"
    },
    "priority": {
      "low": "낮음",
      "medium": "보통",
      "high": "높음",
      "critical": "긴급"
    }
  },
  "processDesigner": {
    "title": "프로세스 디자이너",
    "toolbox": {
      "domain": "부서/사업부",
      "action": "업무 행위",
      "event": "업무 사건",
      "entity": "업무 객체",
      "rule": "업무 규칙",
      "stakeholder": "이해관계자",
      "report": "업무 보고서",
      "measure": "KPI/측정값"
    },
    "mining": {
      "conformance": "적합도 점수",
      "variants": "변형 수",
      "bottleneck": "병목 구간"
    }
  }
}
```

### 7.4 사용 패턴

```typescript
// 컴포넌트에서 사용

import { useTranslation } from 'react-i18next';

function CaseListPage() {
  const { t } = useTranslation();

  return (
    <div>
      <h1>{t('cases.title')}</h1>

      <Button>{t('cases.create')}</Button>

      {/* 보간(interpolation) */}
      <p>{t('cases.totalCount', { count: cases.length })}</p>

      {/* 복수형 */}
      <p>{t('cases.selectedCount', { count: selectedIds.length })}</p>
    </div>
  );
}
```

```typescript
// Zod 스키마에서 i18n 에러 메시지 사용

import i18n from '@/lib/i18n/i18n';

const caseCreateSchema = z.object({
  title: z
    .string()
    .min(1, i18n.t('validation.required', { field: i18n.t('cases.fields.title') })),
});
```

### 7.5 국제화 규칙

#### 필수 (Required)

- 사용자에게 보이는 모든 문자열은 `t()` 함수를 통해 출력한다
- 날짜/숫자/통화 포맷은 `Intl` API를 사용한다 (하드코딩 포맷 금지)
- 새 Feature 추가 시 ko.json, en.json 모두 업데이트한다
- 번역 키는 `feature.section.key` 형태의 계층 구조를 따른다

#### 금지됨 (Forbidden)

- JSX에 한국어 문자열 직접 작성 (`<Button>저장</Button>` -> `<Button>{t('common.save')}</Button>`)
- `Date.toLocaleDateString()` 직접 사용 (공유 포맷 함수 `formatDate()` 사용)
- 번역 파일에 HTML 태그 포함 (`Trans` 컴포넌트가 필요한 경우만 예외)

### 7.6 K-AIR 전환 노트

| K-AIR | Canvas | 변경 사유 |
|-------|--------|-----------|
| vue-i18n | react-i18next | React 생태계 표준 |
| 단일 언어(한국어) 하드코딩 다수 | 모든 문자열 외부화 | 다국어 지원 기반 마련 |
| 날짜 포맷: dayjs 직접 사용 | `Intl.DateTimeFormat` + 유틸 함수 | 로케일 자동 적용 |

---

## 8. 실시간 통신 패턴

### 8.1 왜 이 패턴이 필요한가

Canvas는 세 가지 실시간 통신 방식을 사용한다:

| 방식 | 용도 | 방향 | 프로토콜 |
|------|------|------|----------|
| **WebSocket** | Watch 알림, 실시간 이벤트 | 양방향 | ws:// |
| **SSE** | 장시간 LLM 응답 스트리밍 | 서버 -> 클라이언트 | text/event-stream |
| **Yjs + y-websocket** | 프로세스 디자이너 실시간 협업 | 양방향 (P2P via relay) | ws:// |

### 8.2 WebSocket 패턴

```typescript
// lib/api/wsManager.ts

import { useAuthStore } from '@/stores/authStore';

type WsEventHandler = (data: unknown) => void;

class WsManager {
  private ws: WebSocket | null = null;
  private listeners = new Map<string, Set<WsEventHandler>>();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;     // 지수 백오프 시작값

  connect(url: string) {
    const token = useAuthStore.getState().accessToken;
    this.ws = new WebSocket(`${url}?token=${token}`);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      console.info('[WS] Connected');
    };

    this.ws.onmessage = (event) => {
      const { type, payload } = JSON.parse(event.data);
      const handlers = this.listeners.get(type);
      handlers?.forEach((handler) => handler(payload));
    };

    this.ws.onclose = (event) => {
      if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
        // 지수 백오프 재연결
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
        this.reconnectAttempts++;
        console.warn(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(url), delay);
      }
    };

    this.ws.onerror = (error) => {
      console.error('[WS] Error:', error);
    };
  }

  subscribe(eventType: string, handler: WsEventHandler): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)!.add(handler);

    // 구독 해제 함수 반환
    return () => {
      this.listeners.get(eventType)?.delete(handler);
    };
  }

  send(type: string, payload: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload }));
    }
  }

  disconnect() {
    this.ws?.close(1000, 'Client disconnect');
    this.ws = null;
  }
}

export const wsManager = new WsManager();
```

```typescript
// features/watch-alerts/hooks/useWatchAlerts.ts

import { useEffect, useState } from 'react';
import { wsManager } from '@/lib/api/wsManager';

export function useWatchAlerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    // 구독
    // 이벤트명 컨벤션: {도메인}:{동작} (콜론 구분) — watch-alerts.md §8 참조
    const unsubscribe = wsManager.subscribe('alert:new', (data) => {
      const alert = data as Alert;
      setAlerts((prev) => [alert, ...prev].slice(0, 100)); // 최대 100개 유지
    });

    // 클린업: 컴포넌트 언마운트 시 구독 해제
    return unsubscribe;
  }, []);

  return alerts;
}
```

### 8.3 SSE / NDJSON 스트림 패턴

Canvas는 두 가지 스트리밍 방식을 사용한다:

| 방식 | Content-Type | 용도 | 파싱 |
|------|-------------|------|------|
| **Plain Text SSE** | `text/event-stream` | LLM 텍스트 스트리밍 | 청크 이어붙이기 |
| **NDJSON** | `application/x-ndjson` | ReAct 다단계 추론, 진행 상태 | 줄 단위 JSON 파싱 |

```typescript
// lib/api/streamManager.ts — 통합 스트림 유틸리티

interface StreamOptions<T> {
  /** Plain text: 청크 문자열, NDJSON: 파싱된 객체 */
  onMessage: (data: T) => void;
  onComplete: () => void;
  onError: (error: Error) => void;
}

/**
 * Plain text SSE 스트림 (LLM 응답 등)
 * 각 청크를 문자열로 전달
 */
export async function createTextStream(
  url: string,
  body: Record<string, unknown>,
  options: StreamOptions<string>,
): Promise<AbortController> {
  return createStream(url, body, options, 'text');
}

/**
 * NDJSON 스트림 (ReAct 추론 등)
 * 각 줄을 JSON 파싱하여 객체로 전달
 */
export async function createNdjsonStream<T = Record<string, unknown>>(
  url: string,
  body: Record<string, unknown>,
  options: StreamOptions<T>,
): Promise<AbortController> {
  return createStream(url, body, options, 'ndjson');
}

/** 내부 구현 — 모드에 따라 파싱 전략 분기 */
async function createStream<T>(
  url: string,
  body: Record<string, unknown>,
  options: StreamOptions<T>,
  mode: 'text' | 'ndjson',
): Promise<AbortController> {
  const controller = new AbortController();
  const token = useAuthStore.getState().accessToken;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        Accept: mode === 'ndjson' ? 'application/x-ndjson' : 'text/event-stream',
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Stream failed: ${response.status}`);
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        options.onComplete();
        break;
      }

      const chunk = decoder.decode(value, { stream: true });

      if (mode === 'text') {
        (options.onMessage as (data: string) => void)(chunk);
      } else {
        // NDJSON: 줄 단위 파싱
        buffer += chunk;
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.trim()) continue;
          (options.onMessage as (data: T) => void)(JSON.parse(line));
        }
      }
    }
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      options.onError(error as Error);
    }
  }

  return controller;
}
```

사용 예시 — NL2SQL ReAct 스트림:
```typescript
// features/nl2sql-chat/hooks/useNl2SqlReact.ts

import { createNdjsonStream } from '@/lib/api/streamManager';

// /api/v1/text2sql/react 엔드포인트 (NDJSON)
controllerRef.current = await createNdjsonStream<ReactStep>(
  '/api/v1/text2sql/react',
  { question, datasource_id: datasourceId },
  {
    onMessage: (step) => {
      // step.step: 'select' | 'generate' | 'validate' | ... | 'result' | 'error'
      setState(prev => ({ ...prev, steps: [...prev.steps, step] }));
    },
    onComplete: () => setStreaming(false),
    onError: () => toast.error(t('common.error')),
  },
);
```

### 8.4 Yjs 실시간 협업 패턴

```typescript
// features/process-designer/hooks/useYjsCollaboration.ts

import { useEffect, useRef, useMemo } from 'react';
import * as Y from 'yjs';
import { WebsocketProvider } from 'y-websocket';
import { IndexeddbPersistence } from 'y-indexeddb';
import { useAuthStore } from '@/stores/authStore';

interface CollaborationState {
  ydoc: Y.Doc;
  items: Y.Map<CanvasItem>;
  connections: Y.Map<Connection>;
  positions: Y.Map<{ x: number; y: number }>;
  awareness: WebsocketProvider['awareness'];
}

export function useYjsCollaboration(boardId: string): CollaborationState {
  const ydocRef = useRef<Y.Doc | null>(null);
  const providerRef = useRef<WebsocketProvider | null>(null);
  const user = useAuthStore((s) => s.user);

  const state = useMemo(() => {
    // 기존 연결 정리
    providerRef.current?.disconnect();
    ydocRef.current?.destroy();

    // Yjs Document 생성
    const ydoc = new Y.Doc();
    ydocRef.current = ydoc;

    // 공유 데이터 구조
    const items = ydoc.getMap<CanvasItem>('items');
    const connections = ydoc.getMap<Connection>('connections');
    const positions = ydoc.getMap<{ x: number; y: number }>('positions');

    // WebSocket Provider (서버 동기화)
    const wsUrl = import.meta.env.VITE_YJS_WS_URL;
    const provider = new WebsocketProvider(wsUrl, `board:${boardId}`, ydoc);
    providerRef.current = provider;

    // IndexedDB Persistence (오프라인 지원)
    new IndexeddbPersistence(`board:${boardId}`, ydoc);

    // 내 커서/선택 정보 공유
    provider.awareness.setLocalState({
      userId: user?.id,
      name: user?.name,
      color: generateUserColor(user?.id ?? ''),
      cursor: null,
      selectedItemIds: [],
    });

    return { ydoc, items, connections, positions, awareness: provider.awareness };
  }, [boardId, user?.id, user?.name]);

  // 클린업
  useEffect(() => {
    return () => {
      providerRef.current?.disconnect();
      ydocRef.current?.destroy();
    };
  }, [boardId]);

  return state;
}

/** 사용자 ID에서 결정론적 색상 생성 */
function generateUserColor(userId: string): string {
  const colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c'];
  const hash = userId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return colors[hash % colors.length];
}
```

```typescript
// 커서 위치 업데이트 (throttle 적용)

import { useCallback } from 'react';
import { throttle } from '@/shared/utils/throttle';

export function useCanvasInteraction(awareness: Awareness) {
  // 커서 위치 업데이트는 50ms 간격으로 제한 (네트워크 부하 방지)
  const updateCursor = useCallback(
    throttle((x: number, y: number) => {
      awareness.setLocalStateField('cursor', { x, y });
    }, 50),
    [awareness],
  );

  const updateSelection = useCallback(
    (selectedIds: string[]) => {
      awareness.setLocalStateField('selectedItemIds', selectedIds);
    },
    [awareness],
  );

  return { updateCursor, updateSelection };
}
```

### 8.5 실시간 통신 규칙

#### 필수 (Required)

- WebSocket 연결은 `wsManager` 싱글톤을 통해 관리한다 (다중 연결 방지)
- 재연결은 지수 백오프(exponential backoff)를 적용한다
- SSE 스트림은 컴포넌트 언마운트 시 `AbortController`로 반드시 취소한다
- Yjs 커서 위치 업데이트는 `throttle`(50ms)을 적용한다
- 실시간 데이터는 이벤트 핸들러에서 직접 상태 변경, TanStack Query 캐시는 건드리지 않는다

#### 금지됨 (Forbidden)

- WebSocket을 컴포넌트에서 직접 `new WebSocket()` 생성 (`wsManager` 사용)
- SSE 스트림 취소 없이 페이지 이동 (메모리 누수 원인)
- Yjs Document의 데이터를 Zustand에 복사하여 이중 관리 (Yjs가 단일 진실 원천)
- 실시간 이벤트를 수신할 때마다 전체 리스트를 서버에 다시 요청 (이벤트 데이터로 로컬 업데이트)

### 8.6 K-AIR 전환 노트

| K-AIR | Canvas | 변경 사유 |
|-------|--------|-----------|
| socket.io-client | 네이티브 WebSocket + 커스텀 관리자 | 번들 크기 절감, 서버와 프로토콜 일치 |
| SSE 미사용 (polling) | SSE (text/event-stream) | LLM 스트리밍 응답 실시간 표시 |
| Yjs + y-websocket (Vue) | Yjs + y-websocket (React) | 프레임워크 무관, 로직 그대로 이식 |

---

## 결정 사항 (Decisions)

- **에러 처리**: react-error-boundary + AppError 클래스 기반 통합 에러 처리
  - 근거: 페이지 단위 격리로 한 Feature 에러가 전체 앱을 중단시키지 않음

- **폼 처리**: React Hook Form + Zod
  - 근거: 타입 추론 자동화, 서버 에러 매핑, 성능 (비제어 컴포넌트 기반)

- **테스트**: Vitest + React Testing Library + Playwright 3단 피라미드
  - 근거: Vite 네이티브 테스트 러너(Vitest)로 빌드 설정 공유, Playwright는 크로스 브라우저

- **실시간 통신**: 네이티브 WebSocket (socket.io 제거)
  - 근거: Canvas 백엔드가 네이티브 WS 프로토콜 사용, socket.io 폴백 불필요

---

## 금지됨 (Forbidden) 종합

| 영역 | 금지 항목 |
|------|-----------|
| 에러 | 빈 catch 블록, 콘솔 전용 에러 출력, 스택 트레이스 사용자 노출 |
| 로딩 | 전체 페이지 스피너, `isLoading ? null : ...` 패턴 |
| 폼 | useState 직접 폼 관리, 인라인 유효성 검증 |
| 접근성 | div+onClick (role 없이), color 단독 상태 구분, 양수 tabIndex |
| 테스트 | data-testid 우선 선택, 내부 상태 검증, sleep 대기 |
| 성능 | 무조건적 React.memo, 빈 의존성 배열, 번들 분석 없이 대형 라이브러리 추가 |
| i18n | JSX 한국어 하드코딩, Date.toLocaleDateString 직접 사용 |
| 실시간 | 컴포넌트 내 new WebSocket, SSE 취소 없는 언마운트, Yjs 데이터 이중 관리 |

---

## 필수 (Required) 종합

| 영역 | 필수 항목 |
|------|-----------|
| 에러 | 페이지 ErrorBoundary, AppError 사용, 한국어 에러 메시지 |
| 로딩 | 스켈레톤-콘텐츠 높이 일치, useSuspenseQuery 우선, 낙관적 업데이트 롤백 |
| 폼 | Zod 스키마, z.infer 타입, 서버 422 매핑, isSubmitting 버튼 비활성화 |
| 접근성 | alt 텍스트, label 연결, focus ring 유지, 포커스 트랩, 라우트별 title |
| 테스트 | 유틸 단위 테스트, 컴포넌트 통합 테스트, 핵심 E2E, 사용자 행동 검증 |
| 성능 | 100행+ 가상화, React.lazy 코드 분할, 번들 정기 점검 |
| i18n | t() 함수, Intl API, ko/en 동시 업데이트, 계층형 번역 키 |
| 실시간 | wsManager 싱글톤, 지수 백오프, AbortController, 커서 throttle |

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.0 | Axiom Team | 초기 작성 - 에러 처리, 로딩, 폼, 접근성, 테스트, 성능, i18n, 실시간 통신 패턴 |
