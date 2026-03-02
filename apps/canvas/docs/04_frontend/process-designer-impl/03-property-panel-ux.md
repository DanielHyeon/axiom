# Phase 3: Property Panel 완성 + UX 상태

> 예상 기간: 2-3일
> 선행 조건: Phase 1 완료 (Phase 2와 병렬 가능)
> 설계 문서 섹션: §4 속성 패널, §11 UX 상태 설계

---

## 목표

1. 속성 패널 4개 서브 섹션 완성 (Basic, Temporal, MeasureBinding, EventLogBinding)
2. 노드 타입별 조건부 속성 표시
3. 에러/빈/로딩 상태 패턴 적용
4. 빈 캔버스 안내 + 연결 상태 배너

---

## Step 3.1: 기본 속성 패널 완성

**파일**: `features/process-designer/components/property-panel/BasicProperties.tsx`

### 작업 내용

기존 `PropertyPanel.tsx`의 기본 속성을 확장한다.

| 필드 | 타입 | 비고 |
|------|------|------|
| 이름 (label) | text input | 기존 구현 유지 |
| 설명 (description) | textarea | **신규** |
| 타입 | 읽기전용 표시 | 기존 유지 |
| 색상 | color picker 또는 읽기전용 | 타입별 고정 색상이므로 읽기전용 |
| 위치 (x, y) | 읽기전용 | 기존 유지 |
| 크기 (width, height) | number input | **신규** |
| 소속 Domain | select (contextBox 목록) | **신규** — `parentContextBoxId` |

```typescript
interface BasicPropertiesProps {
  item: CanvasItem;
  contextBoxes: CanvasItem[];  // type === 'contextBox'인 항목 목록
  onUpdate: (id: string, updates: Partial<CanvasItem>) => void;
}
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 3.1.1 | 설명 필드에 텍스트 입력·저장 가능 | 브라우저 확인 |
| 3.1.2 | 크기(width, height) 숫자 입력·저장 가능 | 브라우저 확인 |
| 3.1.3 | 소속 Domain 드롭다운에서 contextBox 목록 표시 | 브라우저 확인 |
| 3.1.4 | 소속 Domain 변경 시 `parentContextBoxId` 업데이트 | 데이터 확인 |

---

## Step 3.2: 시간축 속성 패널

**파일**: `features/process-designer/components/property-panel/TemporalProperties.tsx`

### 작업 내용

설계 §4.1 — `businessEvent`, `businessAction` 노드 선택 시 표시.

```typescript
interface TemporalPropertiesProps {
  temporal: TemporalData | undefined;
  onUpdate: (temporal: TemporalData) => void;
}
```

| 필드 | 타입 | 비고 |
|------|------|------|
| 예상 소요 (expectedDuration) | number input + "분" 단위 | 사용자 입력 |
| SLA (sla) | number input + "분" 단위 | 사용자 입력 |
| 실제 평균 (actualAvg) | 읽기전용 + "분" 단위 | Phase 5 마이닝 결과 |
| 상태 (status) | 자동 계산 뱃지 | `ok`=초록, `warning`=주황, `violation`=빨강 |

**상태 자동 계산 로직:**
```typescript
function computeTemporalStatus(t: TemporalData): 'ok' | 'warning' | 'violation' | undefined {
  if (t.actualAvg == null || t.expectedDuration == null || t.sla == null) return undefined;
  if (t.actualAvg <= t.expectedDuration) return 'ok';
  if (t.actualAvg <= t.sla) return 'warning';
  return 'violation';
}
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 3.2.1 | `businessEvent` 선택 시 시간축 패널 표시 | 브라우저 확인 |
| 3.2.2 | `businessAction` 선택 시 시간축 패널 표시 | 브라우저 확인 |
| 3.2.3 | `businessEntity` 선택 시 시간축 패널 미표시 | 브라우저 확인 |
| 3.2.4 | 예상 소요·SLA 입력 시 값 저장 | 데이터 확인 |
| 3.2.5 | 실제 평균이 SLA 초과 시 빨간 `violation` 뱃지 표시 | 수동 테스트 데이터 |
| 3.2.6 | 실제 평균이 없으면 상태 뱃지 미표시 | 브라우저 확인 |

---

## Step 3.3: 측정값 바인딩 패널

**파일**: `features/process-designer/components/property-panel/MeasureBinding.tsx`

### 작업 내용

설계 §4.2 — `measure` 노드 선택 시 표시.

```typescript
interface MeasureBindingProps {
  binding: MeasureBindingData | undefined;
  onUpdate: (binding: MeasureBindingData) => void;
}
```

| 필드 | 타입 | 비고 |
|------|------|------|
| KPI ID (kpiId) | select (온톨로지 KPI 목록) | Phase 5에서 API 연동, 임시: 텍스트 입력 |
| 공식 (formula) | text input | 예: "count(입고접수완료) / count(입고요청)" |
| 단위 (unit) | text input | %, 건, 시간 등 |

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 3.3.1 | `measure` 노드 선택 시 측정값 바인딩 패널 표시 | 브라우저 확인 |
| 3.3.2 | 다른 노드 타입 선택 시 미표시 | 브라우저 확인 |
| 3.3.3 | 공식·단위 입력·저장 가능 | 데이터 확인 |

---

## Step 3.4: 이벤트 로그 바인딩 패널

**파일**: `features/process-designer/components/property-panel/EventLogBinding.tsx`

### 작업 내용

설계 §4.3 — `eventLogBinding` 노드 선택 시 표시.

```typescript
interface EventLogBindingProps {
  binding: EventLogBindingData | undefined;
  onUpdate: (binding: EventLogBindingData) => void;
}
```

| 필드 | 타입 | 비고 |
|------|------|------|
| 소스 테이블 (sourceTable) | select | Phase 5에서 Weaver 메타데이터 연동, 임시: 텍스트 |
| 타임스탬프 컬럼 (timestampColumn) | select | 상동 |
| 케이스 ID 컬럼 (caseIdColumn) | select | 상동 |
| 활동명 컬럼 (activityColumn) | select (선택) | 상동 |
| 필터 (filter) | text input | SQL WHERE 조건 |

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 3.4.1 | `eventLogBinding` 노드 선택 시 로그 바인딩 패널 표시 | 브라우저 확인 |
| 3.4.2 | 다른 노드 타입 선택 시 미표시 | 브라우저 확인 |
| 3.4.3 | 5개 필드 입력·저장 가능 | 데이터 확인 |

---

## Step 3.5: 속성 패널 컨테이너

**파일**: `features/process-designer/components/property-panel/ProcessPropertyPanel.tsx`

### 작업 내용

노드 타입에 따라 표시할 서브 패널을 결정하는 컨테이너.

```typescript
export function ProcessPropertyPanel({ selectedItem, onUpdate }: Props) {
  if (!selectedItem) {
    return <NoSelectionPlaceholder />;
  }

  return (
    <div className="w-80 border-l border-neutral-800 bg-neutral-900 flex flex-col overflow-auto">
      <PanelHeader item={selectedItem} />
      <BasicProperties item={selectedItem} onUpdate={onUpdate} />

      {/* businessEvent, businessAction에만 표시 */}
      {(['businessEvent', 'businessAction'] as const).includes(selectedItem.type) && (
        <TemporalProperties temporal={selectedItem.temporal} onUpdate={...} />
      )}

      {/* measure에만 표시 */}
      {selectedItem.type === 'measure' && (
        <MeasureBinding binding={selectedItem.measureBinding} onUpdate={...} />
      )}

      {/* eventLogBinding에만 표시 */}
      {selectedItem.type === 'eventLogBinding' && (
        <EventLogBinding binding={selectedItem.eventLogBinding} onUpdate={...} />
      )}
    </div>
  );
}
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 3.5.1 | 노드 미선택 시 "노드를 선택하세요" 안내 표시 | 브라우저 확인 |
| 3.5.2 | `businessEvent` 선택 → 기본 + 시간축 패널 표시 | 브라우저 확인 |
| 3.5.3 | `measure` 선택 → 기본 + 측정값 바인딩 패널 표시 | 브라우저 확인 |
| 3.5.4 | `eventLogBinding` 선택 → 기본 + 로그 바인딩 패널 표시 | 브라우저 확인 |
| 3.5.5 | `stakeholder` 선택 → 기본 패널만 표시 | 브라우저 확인 |

---

## Step 3.6: UX 상태 — 캔버스 영역

### 빈 캔버스 안내 (설계 §11.2)

노드가 0개일 때 캔버스 중앙에 안내 표시:

```tsx
{items.length === 0 && (
  <div className="absolute inset-0 flex items-center justify-center">
    <div className="text-center text-neutral-500">
      <Workflow className="w-12 h-12 mx-auto mb-3 opacity-30" />
      <p className="text-sm font-medium">도구 상자에서 노드를 드래그하여</p>
      <p className="text-sm font-medium">프로세스를 설계하세요</p>
      <p className="text-xs mt-2 text-neutral-600">
        또는 키보드 단축키(B, E, N, R)를 사용하세요
      </p>
    </div>
  </div>
)}
```

### 캔버스 초기 로드 (설계 §11.3)

보드 데이터 로딩 중 스피너:

```tsx
{boardLoading && (
  <div className="absolute inset-0 flex items-center justify-center bg-neutral-950/80">
    <Loader2 className="w-8 h-8 animate-spin text-neutral-400" />
    <span className="ml-2 text-sm text-neutral-400">보드를 불러오는 중...</span>
  </div>
)}
```

### 현재 도구 모드 표시

캔버스 상단 좌측에 현재 도구 모드를 표시하는 뱃지:

```tsx
<div className="absolute top-4 left-4 bg-neutral-900/80 px-3 py-1.5 rounded text-xs">
  {toolMode === 'select' ? '선택 모드' :
   toolMode === 'connect' ? '🔗 연결선 모드 (ESC로 취소)' :
   `✏️ ${NODE_CONFIGS[toolMode].labelKo} 추가 모드`}
</div>
```

### 통과 기준

| # | 기준 | 검증 |
|:-:|------|------|
| 3.6.1 | 빈 캔버스에 안내 메시지 + 아이콘 표시 | 브라우저 확인 |
| 3.6.2 | 노드 추가 후 안내 메시지 사라짐 | 브라우저 확인 |
| 3.6.3 | 보드 로딩 중 스피너 표시 | 느린 네트워크 시뮬레이션 |
| 3.6.4 | 현재 도구 모드가 상단 뱃지에 표시 | 각 모드 전환 시 확인 |

---

## Phase 3 완료 체크리스트

| # | 항목 | 완료 |
|:-:|------|:----:|
| 1 | `BasicProperties.tsx` — 설명, 크기, 소속 Domain 추가 | [ ] |
| 2 | `TemporalProperties.tsx` — 시간축 속성 4필드 | [ ] |
| 3 | `MeasureBinding.tsx` — KPI, 공식, 단위 | [ ] |
| 4 | `EventLogBinding.tsx` — 5필드 | [ ] |
| 5 | `ProcessPropertyPanel.tsx` — 타입별 조건부 표시 | [ ] |
| 6 | 빈 캔버스 안내 메시지 | [ ] |
| 7 | 보드 로딩 스피너 | [ ] |
| 8 | 도구 모드 뱃지 | [ ] |
| 9 | `tsc --noEmit` 빌드 에러 0건 | [ ] |
