# 디자인 시스템

<!-- affects: frontend -->
<!-- requires-update: 01_architecture/component-architecture.md -->
<!-- 구현: Phase E 완료 — Design Tokens(src/styles/tokens.css), themeStore, ThemeProvider, 다크 모드 전역(.dark), Header 테마 전환 -->

## 이 문서가 답하는 질문

- Canvas의 디자인 시스템은 어떻게 구성되는가?
- Shadcn/ui + Tailwind CSS를 어떻게 활용하는가?
- 다크 모드는 어떻게 구현하는가?
- K-AIR의 Vuetify + Tailwind + Headless UI 혼재 문제를 어떻게 해결하는가?

---

## 1. 디자인 시스템 아키텍처

```
┌───────────────────────────────────────────────────────────────┐
│  Canvas 디자인 시스템                                          │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Design Tokens (CSS Variables)                           │  │
│  │  - 색상, 타이포그래피, 간격, 반경, 그림자               │  │
│  │  - 라이트/다크 모드 전환                                 │  │
│  ├─────────────────────────────────────────────────────────┤  │
│  │  Shadcn/ui Primitives (shared/ui/)                      │  │
│  │  - Button, Card, Dialog, Input, Select, Table, ...      │  │
│  │  - Radix UI 기반 접근성 보장                             │  │
│  │  - 소유 가능(copy-paste), 커스터마이징 자유              │  │
│  ├─────────────────────────────────────────────────────────┤  │
│  │  Custom Components (shared/components/)                  │  │
│  │  - DataTable, Chart, StatusBadge, EmptyState, ...       │  │
│  │  - Shadcn/ui 위에 비즈니스 패턴 적용                    │  │
│  ├─────────────────────────────────────────────────────────┤  │
│  │  Feature Components (features/*/components/)             │  │
│  │  - 도메인 특화 UI (PivotBuilder, GraphViewer, ...)      │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

---

## 2. 디자인 토큰

### 2.1 색상 체계

```css
/* styles/globals.css */

@layer base {
  :root {
    /* 배경 */
    --background: 0 0% 100%;          /* 흰색 */
    --foreground: 222.2 84% 4.9%;     /* 거의 검정 */

    /* 카드/팝오버 */
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;

    /* 주요 색상 (Axiom 브랜드) */
    --primary: 221.2 83.2% 53.3%;     /* 파랑 계열 */
    --primary-foreground: 210 40% 98%;

    /* 보조 색상 */
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;

    /* 상태 색상 */
    --destructive: 0 84.2% 60.2%;     /* 빨강 (에러/삭제) */
    --success: 142 76% 36%;           /* 초록 (성공) */
    --warning: 38 92% 50%;            /* 주황 (경고) */
    --info: 221 83% 53%;             /* 파랑 (정보) */

    /* UI 요소 */
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 221.2 83.2% 53.3%;

    /* 사이드바 */
    --sidebar-background: 0 0% 98%;
    --sidebar-foreground: 240 5.3% 26.1%;
    --sidebar-border: 220 13% 91%;
    --sidebar-accent: 220 14.3% 95.9%;

    /* 반경 */
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;

    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;

    --primary: 217.2 91.2% 59.8%;
    --primary-foreground: 222.2 47.4% 11.2%;

    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;

    --destructive: 0 62.8% 30.6%;
    --success: 142 76% 26%;
    --warning: 38 92% 40%;

    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 224.3 76.3% 48%;

    --sidebar-background: 240 5.9% 10%;
    --sidebar-foreground: 240 4.8% 95.9%;
  }
}
```

### 2.2 타이포그래피

```css
/* 한글 최적화 폰트 스택 */
--font-sans: 'Pretendard Variable', 'Pretendard',
             -apple-system, BlinkMacSystemFont,
             system-ui, Roboto,
             'Helvetica Neue', 'Segoe UI',
             'Malgun Gothic', sans-serif;

--font-mono: 'JetBrains Mono', 'Fira Code',
             'Source Code Pro', monospace;
```

| 용도 | 클래스 | 크기 | 무게 |
|------|--------|------|------|
| 페이지 제목 | `text-2xl font-bold` | 1.5rem | 700 |
| 섹션 제목 | `text-xl font-semibold` | 1.25rem | 600 |
| 카드 제목 | `text-lg font-medium` | 1.125rem | 500 |
| 본문 | `text-sm` | 0.875rem | 400 |
| 캡션 | `text-xs text-muted-foreground` | 0.75rem | 400 |
| 코드/SQL | `font-mono text-sm` | 0.875rem | 400 |

### 2.3 간격(Spacing) 체계

```
Tailwind 간격 스케일 사용:
1 = 0.25rem (4px)
2 = 0.5rem  (8px)
3 = 0.75rem (12px)
4 = 1rem    (16px)
6 = 1.5rem  (24px)
8 = 2rem    (32px)

컴포넌트 간 간격: gap-4 (16px) 기본
섹션 간 간격: gap-6 (24px)
페이지 패딩: p-6 (24px)
카드 패딩: p-4 (16px)
```

---

## 3. 다크 모드

### 3.1 구현 방식

```typescript
// stores/themeStore.ts

interface ThemeStore {
  mode: 'light' | 'dark' | 'system';
  resolved: 'light' | 'dark';   // 실제 적용된 테마

  setMode: (mode: ThemeMode) => void;
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      mode: 'system',
      resolved: 'light',
      setMode: (mode) => {
        const resolved = mode === 'system'
          ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
          : mode;

        // HTML 클래스 토글
        document.documentElement.classList.toggle('dark', resolved === 'dark');

        set({ mode, resolved });
      },
    }),
    { name: 'axiom-theme' },
  ),
);
```

### 3.2 다크 모드 규칙

#### 필수 (Required)
- 모든 색상은 CSS 변수 사용 (하드코딩 금지)
- `bg-background`, `text-foreground` 등 시맨틱 클래스 사용
- 차트 색상도 CSS 변수 참조

#### 금지됨 (Forbidden)
- `bg-white`, `text-black` 등 절대 색상 직접 사용
- 인라인 스타일에 색상 하드코딩
- 이미지에 흰색 배경 포함 (투명 배경 사용)

---

## 4. 컴포넌트 패턴

### 4.1 상태별 색상 배지

```typescript
// shared/components/StatusBadge.tsx

import { cva, type VariantProps } from 'class-variance-authority';

/** StatusBadge — 케이스, 문서, 워크아이템, 시나리오, 데이터소스 등 전역 상태 표시 */

const statusBadgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium',
  {
    variants: {
      status: {
        // 케이스 상태
        draft:            'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
        filed:            'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
        in_progress:      'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
        review:           'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
        approved:         'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
        rejected:         'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
        closed:           'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
        // 문서 리뷰 상태
        in_review:        'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
        changes_requested:'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300',
        archived:         'bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500',
        // What-if 시나리오 상태
        computing:        'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
        completed:        'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
        failed:           'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
        // 데이터소스 연결 상태
        connected:        'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
        syncing:          'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
        error:            'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
        // 알림 우선순위
        critical:         'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
        warning:          'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
        info:             'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
      },
    },
  },
);

type StatusBadgeProps = VariantProps<typeof statusBadgeVariants> & {
  label: string;
  icon?: React.ReactNode;
};

export function StatusBadge({ status, label, icon }: StatusBadgeProps) {
  return (
    <span className={statusBadgeVariants({ status })}>
      {icon}
      {label}
    </span>
  );
}
```

> **사용 규칙**: 새 도메인에 상태 배지가 필요하면 `statusBadgeVariants.variants.status`에 추가하고, 이 문서의 목록을 갱신한다. 색상 중복은 허용한다 (같은 의미면 같은 색상 — 예: `approved`와 `completed`는 둘 다 초록색).
```

### 4.2 반응형 레이아웃

```
모바일 (< 768px):   사이드바 숨김, 햄버거 메뉴
태블릿 (768-1024):  사이드바 축소 (아이콘만)
데스크톱 (> 1024):  사이드바 펼침 (아이콘 + 텍스트)
와이드 (> 1440):    콘텐츠 최대 너비 제한 (max-w-7xl)
```

---

## 5. K-AIR 디자인 시스템 문제와 해결

| K-AIR 문제 | Canvas 해결 |
|------------|-------------|
| Vuetify Material + Tailwind + Headless UI 3종 혼재 | Shadcn/ui + Tailwind 단일 시스템 |
| 다크 모드: 부분 지원 (Vuetify만) | CSS 변수 기반 전체 다크 모드 |
| 한글 폰트: 시스템 기본 | Pretendard Variable |
| 컴포넌트 스타일: 라이브러리 제약 | 소유 가능(copy-paste) 컴포넌트 |
| 반응형: 부분 적용 | Tailwind 브레이크포인트 전체 적용 |

---

## 결정 사항 (Decisions)

- Shadcn/ui를 디자인 시스템 기반으로 선택
  - 근거: ADR-002 참조
  - 핵심: 소유 가능한 컴포넌트 -> 도메인 커스텀 자유도

- Pretendard 폰트 사용
  - 근거: 한글 가독성 최적화, Variable Font로 번들 크기 최소화

- 3단계 테마: light / dark / system
  - 근거: 사용자 OS 설정 존중 + 수동 선택 가능

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.1 | Axiom Team | StatusBadge cva 기반 타입 안전한 variant 시스템으로 확장 (문서/시나리오/데이터소스/알림 상태 포함) |
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
