# Phase 5: 프로세스 마이닝 오버레이 + AI 역공학

> 예상 기간: 4-5일
> 선행 조건: Phase 4 완료 (Yjs 데이터 계층)
> 설계 문서 섹션: §5 프로세스 마이닝 결과 오버레이, §7 AI 역공학

---

## 목표

1. Synapse API 연동 (`useProcessMining` hook)
2. 캔버스 위 적합성/병목/이탈 경로 오버레이 렌더링
3. 변형 목록 패널 (VariantList)
4. AI 역공학: 이벤트 로그 → 프로세스 모델 자동 생성

---

## Step 5.1: Synapse API 클라이언트

**파일**: `features/process-designer/api/processDesignerApi.ts`

### 작업 내용

설계 §5.2의 3개 Synapse 엔드포인트에 대한 API 클라이언트.

```typescript
import { synapseApi } from '@/lib/api/clients';

// 1. 프로세스 발견 (pm4py)
export interface DiscoverRequest {
  sourceTable: string;
  timestampColumn: string;
  caseIdColumn: string;
  activityColumn: string;
  algorithm?: 'alpha' | 'inductive' | 'heuristic';
}

export interface DiscoveredProcess {
  activities: Array<{
    name: string;
    frequency: number;
    isStart: boolean;
    isEnd: boolean;
  }>;
  transitions: Array<{
    source: string;
    target: string;
    frequency: number;
  }>;
}

export async function discoverProcess(req: DiscoverRequest): Promise<DiscoveredProcess> {
  return synapseApi.post('/process-mining/discover', req);
}

// 2. 적합도 검사
export interface ConformanceResult {
  fitnessScore: number;     // 0-100
  deviations: Array<{
    path: string[];          // 이탈 경로 노드 이름 목록
    frequency: number;       // 빈도
    percentage: number;      // 전체 대비 비율
  }>;
}

export async function getConformance(
  boardId: string,
  bindings: EventLogBindingData[]
): Promise<ConformanceResult> {
  return synapseApi.get(`/process-mining/conformance`, { params: { boardId } });
}

// 3. 병목 분석
export interface BottleneckResult {
  bottlenecks: Array<{
    activityName: string;
    avgWaitTime: number;     // 분
    slaViolationRate: number; // 0-1
    severity: 'low' | 'medium' | 'high';
  }>;
}

export async function getBottlenecks(
  boardId: string,
  bindings: EventLogBindingData[]
): Promise<BottleneckResult> {
  return synapseApi.get(`/process-mining/bottleneck`, { params: { boardId } });
}
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 5.1.1 | 3개 API 함수 TypeScript 타입 정의 완료 | `tsc --noEmit` |
| 5.1.2 | API 호출 시 올바른 엔드포인트 + 파라미터 전달 | mock 테스트 |

---

## Step 5.2: useProcessMining Hook

**파일**: `features/process-designer/hooks/useProcessMining.ts`

### 작업 내용

설계 §5.2의 데이터 흐름을 구현한다. 설계 Required: "프로세스 마이닝 API를 컴포넌트에서 직접 호출 금지, 반드시 useProcessMining hook을 통해".

```typescript
interface UseProcessMiningOptions {
  boardId: string;
  bindings: EventLogBindingData[];
  enabled: boolean;  // 오버레이 표시 토글
}

interface UseProcessMiningReturn {
  // 결과 데이터
  conformance: ConformanceResult | null;
  bottlenecks: BottleneckResult | null;

  // 상태
  loading: boolean;
  error: string | null;

  // 액션
  refresh: () => void;
  toggleOverlay: () => void;
  overlayVisible: boolean;
}
```

내부적으로 TanStack Query 사용:
```typescript
const conformanceQuery = useQuery({
  queryKey: ['process-mining', 'conformance', boardId],
  queryFn: () => getConformance(boardId, bindings),
  enabled,
});

const bottleneckQuery = useQuery({
  queryKey: ['process-mining', 'bottleneck', boardId],
  queryFn: () => getBottlenecks(boardId, bindings),
  enabled,
});
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 5.2.1 | 바인딩 설정 후 마이닝 결과 자동 조회 | API 호출 확인 |
| 5.2.2 | 로딩/에러/성공 상태 정상 반환 | 각 상태 시뮬레이션 |
| 5.2.3 | `toggleOverlay()`로 오버레이 표시/숨김 전환 | 브라우저 확인 |
| 5.2.4 | `refresh()`로 수동 재조회 | 브라우저 확인 |

---

## Step 5.3: ConformanceOverlay 실제 구현

**파일**: `features/process-designer/components/mining/ConformanceOverlay.tsx`

### 작업 내용

기존 스텁을 실제 캔버스 오버레이로 교체한다. 설계 §5.1의 시각화 규칙.

**3가지 오버레이 요소:**

#### (a) BottleneckHighlight

```typescript
// 병목 노드에 반투명 빨간 배경 + ⚠ 아이콘 표시
<Rect
  x={node.x - 4}
  y={node.y - 4}
  width={node.width + 8}
  height={node.height + 8}
  fill="rgba(239, 68, 68, 0.15)"
  stroke="#ef4444"
  strokeWidth={2}
  cornerRadius={6}
  dash={severity === 'high' ? undefined : [8, 4]}
/>
```

#### (b) DeviationPath

```typescript
// 이탈 경로를 점선으로 표시
<Arrow
  points={deviationPoints}
  stroke="#94a3b8"
  strokeWidth={deviationFrequency * 0.5}  // 빈도 비례
  dash={[10, 5]}
  opacity={0.6}
/>
```

#### (c) EdgeFrequency

```typescript
// 연결선 위에 빈도/소요시간 라벨
<Text
  x={midpointX}
  y={midpointY}
  text={`${frequency}건 / ${avgTime}분`}
  fontSize={10}
  fill="#94a3b8"
/>
```

**색상 범례 (설계 §5.1):**
- 초록: SLA 이내
- 주황: SLA 근접
- 빨강: SLA 위반
- 선 두께: 빈도 비례

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 5.3.1 | 병목 노드에 빨간 하이라이트 + ⚠ 아이콘 | mock 데이터 + 브라우저 |
| 5.3.2 | 이탈 경로가 점선으로 표시 | mock 데이터 + 브라우저 |
| 5.3.3 | 선 두께가 빈도에 비례 | mock 데이터 + 브라우저 |
| 5.3.4 | 오버레이 토글 시 표시/숨김 | 브라우저 확인 |
| 5.3.5 | SLA 상태에 따른 색상 분기 (초록/주황/빨강) | mock 데이터 |

---

## Step 5.4: ConformanceScore + VariantList 실제 구현

**파일**: `features/process-designer/components/mining/ConformanceScore.tsx`

```tsx
// 적합도 점수 (원형 게이지)
<div className="text-center">
  <div className="text-3xl font-bold" style={{ color: scoreColor }}>
    {fitnessScore.toFixed(1)}%
  </div>
  <div className="text-xs text-neutral-400">적합도 점수</div>
</div>
```

**파일**: `features/process-designer/components/mining/VariantList.tsx`

기존 스텁을 실제 변형 목록으로 교체한다.

```typescript
interface VariantListProps {
  conformance: ConformanceResult | null;
  selectedVariant: number | null;
  onSelectVariant: (index: number | null) => void;
}
```

| UI 요소 | 설명 |
|---------|------|
| 변형 항목 | 이름 + 빈도 + 백분율 바 |
| 선택 시 | 해당 경로를 캔버스에 하이라이트 |
| 정상 흐름 | 녹색 바 |
| 이탈 흐름 | 빨간/주황 바 |

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 5.4.1 | 적합도 점수 숫자 + 색상 표시 | mock 데이터 + 브라우저 |
| 5.4.2 | 변형 목록 빈도순 정렬 | 브라우저 확인 |
| 5.4.3 | 변형 클릭 시 캔버스 경로 하이라이트 | 브라우저 확인 |
| 5.4.4 | 마이닝 데이터 없을 때 안내 메시지 (설계 §11.2) | 브라우저 확인 |

---

## Step 5.5: AI 역공학 — 이벤트 로그 → 프로세스 모델

### 작업 내용

설계 §7 — "AI 프로세스 발견" 기능.

**흐름:**
1. 사용자가 빈 캔버스에서 "AI 프로세스 발견" 버튼 클릭
2. 이벤트 로그 소스 선택 다이얼로그 (Weaver 메타데이터 기반)
3. `discoverProcess()` API 호출
4. 응답의 activities → `businessEvent` 노드 자동 생성
5. 응답의 transitions → `Connection` 자동 생성
6. 자동 레이아웃 (좌→우 방향, 노드 간격 200px)

**파일**: `features/process-designer/components/AiDiscoverDialog.tsx`

```typescript
interface AiDiscoverDialogProps {
  open: boolean;
  onClose: () => void;
  onDiscover: (result: DiscoveredProcess) => void;
}
```

**파일**: `features/process-designer/utils/autoLayout.ts`

```typescript
/**
 * 발견된 프로세스를 캔버스 노드/연결선으로 변환하고 자동 배치.
 * 설계 §7.2 pm4py → Canvas 매핑 규칙 적용.
 */
export function layoutDiscoveredProcess(
  discovered: DiscoveredProcess,
): { items: Omit<CanvasItem, 'id'>[]; connections: Omit<Connection, 'id'>[] } {
  // Activity → businessEvent 노드 (설계: 활동명 → 라벨, 빈도 → 크기)
  // Start Activity → 녹색 테두리
  // End Activity → 빨간 테두리
  // Transition → triggers 연결선 (빈도 → 선 두께)
}
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 5.5.1 | "AI 프로세스 발견" 버튼이 빈 캔버스에서 표시 | 브라우저 확인 |
| 5.5.2 | 데이터 소스 선택 다이얼로그 표시 | 브라우저 확인 |
| 5.5.3 | API 호출 중 단계별 진행 표시 (설계 §11.3) | 브라우저 확인 |
| 5.5.4 | 결과가 캔버스에 노드 + 연결선으로 자동 배치 | mock API 응답 |
| 5.5.5 | Start Activity에 녹색 테두리, End에 빨간 테두리 | 브라우저 확인 |
| 5.5.6 | 빈도가 높은 연결선이 더 두꺼움 | 브라우저 확인 |
| 5.5.7 | API 실패 시 에러 메시지 (설계 §11.1) | API 에러 시뮬레이션 |

---

## Phase 5 완료 체크리스트

| # | 항목 | 완료 |
|:-:|------|:----:|
| 1 | `processDesignerApi.ts` — 3개 Synapse 엔드포인트 | [ ] |
| 2 | `useProcessMining.ts` — 마이닝 결과 조회 hook | [ ] |
| 3 | `ConformanceOverlay.tsx` — 병목 + 이탈 경로 오버레이 | [ ] |
| 4 | `ConformanceScore.tsx` — 적합도 점수 게이지 | [ ] |
| 5 | `VariantList.tsx` — 변형 목록 (클릭 시 하이라이트) | [ ] |
| 6 | `AiDiscoverDialog.tsx` — AI 역공학 다이얼로그 | [ ] |
| 7 | `autoLayout.ts` — pm4py 결과 → 캔버스 변환 | [ ] |
| 8 | 마이닝 데이터 없음 빈 상태 | [ ] |
| 9 | API 에러 상태 | [ ] |
| 10 | 분석 진행 중 로딩 상태 (스피너 + 진행률) | [ ] |
