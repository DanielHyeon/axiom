# OLAP 피벗 테이블 UI

<!-- affects: frontend, api -->
<!-- requires-update: 02_api/api-contracts.md (Vision API) -->

## 이 문서가 답하는 질문

- OLAP 피벗 테이블의 화면 구성은 어떻게 되는가?
- 차원/측정값 드래그앤드롭은 어떻게 동작하는가?
- 드릴다운/드릴업은 어떤 인터랙션인가?
- K-AIR PivotEditor/PivotTable의 React 전환 전략은?

---

## 1. 화면 와이어프레임

```
┌──────────────────────────────────────────────────────────────────────┐
│ 📊 OLAP 피벗 분석                                                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── 큐브 선택 ───┐  ┌──── 차원/측정값 팔레트 ──────────────────┐ │
│  │ [재무제표 분석 ▼]│  │                                          │ │
│  └──────────────────┘  │  차원:  [기간] [프로세스유형] [부서] [상태]  │ │
│                         │  측정값: [비용합계] [이해관계자수] [달성률]  │ │
│                         └──────────────────────────────────────────┘ │
│                              ↕ 드래그앤드롭 ↕                        │
│  ┌──── 피벗 빌더 ───────────────────────────────────────────────┐   │
│  │                                                               │   │
│  │  행(Rows):     [기간     ×] [프로세스유형  ×]                  │   │
│  │  열(Columns):  [부서     ×]                                   │   │
│  │  측정값:       [비용합계 ×] [이해관계자수  ×]                 │   │
│  │  필터:         [상태 = 진행중 ×]                               │   │
│  │                                                               │   │
│  │  [행↔열 전환]  [필터 초기화]  [쿼리 실행 →]                   │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──── 결과 영역 ───────────────────────────────────────────────┐   │
│  │                                                               │   │
│  │  [테이블] [바 차트] [라인 차트]  [내보내기 CSV]               │   │
│  │                                                               │   │
│  │  경로: 전체 > 2024년 > Q1                    [드릴업 ↑]      │   │
│  │                                                               │   │
│  │  ┌────────────┬─────────────────────────────────────┐        │   │
│  │  │             │        서울본사                      │        │   │
│  │  │             ├──────────────┬──────────────────────┤        │   │
│  │  │             │ 비용합계(억) │ 이해관계자수          │        │   │
│  │  ├────────────┼──────────────┼──────────────────────┤        │   │
│  │  │ 2024 Q1    │              │                       │        │   │
│  │  │  ├ 분석    │      1,234   │         45            │        │   │
│  │  │  └ 최적화  │      2,567 ↓ │         23            │        │   │
│  │  │ 2024 Q2    │              │                       │        │   │
│  │  │  ├ 분석    │        987   │         38            │        │   │
│  │  │  └ 최적화  │      3,102   │         31            │        │   │
│  │  ├────────────┼──────────────┼──────────────────────┤        │   │
│  │  │ 합계       │      7,890   │        137            │        │   │
│  │  └────────────┴──────────────┴──────────────────────┘        │   │
│  │                                                               │   │
│  │  ↓ = 클릭 시 드릴다운 (Q1 > 1월, 2월, 3월)                  │   │
│  │  쿼리 시간: 1.2초 │ 행: 4 │ 열: 2                            │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. 드래그앤드롭 인터랙션

### 2.1 DnD 영역 정의

```
┌─── 팔레트 (소스) ──────────────────┐
│ 차원:  [기간] [프로세스유형] [부서]  │  ← 여기서 드래그
│ 측정값: [비용합계] [이해관계자수]   │
└────────────────────────────────────┘
                  │ 드래그
                  ▼
┌─── 빌더 (타겟) ──────────────────────────┐
│ 행(Rows):     [드롭 영역              ]  │  ← 여기에 드롭
│ 열(Columns):  [드롭 영역              ]  │
│ 측정값:       [드롭 영역              ]  │
│ 필터:         [드롭 영역              ]  │
└──────────────────────────────────────────┘
```

### 2.2 DnD 규칙

| 규칙 | 설명 |
|------|------|
| 차원은 행/열/필터에 드롭 가능 | 측정값 영역에는 불가 |
| 측정값은 측정값 영역에만 드롭 | 행/열/필터에는 불가 |
| 같은 항목 중복 배치 불가 | 이미 배치된 항목은 팔레트에서 비활성 |
| 빌더 내 항목 순서 변경 가능 | 행 내에서 드래그로 재정렬 |
| × 버튼으로 제거 | 팔레트로 복귀 |

### 2.3 DnD 라이브러리: @dnd-kit

```typescript
// K-AIR: vue-draggable (Sortable.js 래퍼)
// Canvas: @dnd-kit/core + @dnd-kit/sortable

// @dnd-kit 선택 이유:
// - React 네이티브 (DOM 직접 조작 안함)
// - 접근성 (키보드 DnD 지원)
// - 가볍고 트리 셰이킹 가능
```

---

## 3. 드릴다운/드릴업

### 3.1 드릴다운 흐름

```
전체 (Grand Total)
  │ 셀 클릭
  ▼
2024년
  │ 셀 클릭
  ▼
2024년 Q1
  │ 셀 클릭
  ▼
2024년 1월  (계층 최하위 - 더 이상 드릴다운 불가)
```

### 3.2 드릴다운 Breadcrumb

```
전체 > 2024년 > Q1 > 1월
                      └── 현재 위치

[드릴업 ↑] 클릭 → Q1로 복귀
Breadcrumb "2024년" 클릭 → 2024년 전체로 복귀
```

### 3.3 드릴다운 API 호출

```typescript
// 드릴다운 시 추가 필터로 재조회
const drilldown = (dimensionId: string, value: string) => {
  setPivotConfig(prev => ({
    ...prev,
    drilldownPath: [...prev.drilldownPath, { dimensionId, value }],
  }));
  // 자동으로 OLAP 쿼리 재실행 (TanStack Query)
};
```

---

## 4. 컴포넌트 분해

```
OlapPivotPage
├── CubeSelector                      # 큐브 선택 드롭다운
│   └── shared/ui/Select
├── DimensionPalette                  # 차원/측정값 팔레트
│   ├── DraggableDimension (x N)     # @dnd-kit Draggable
│   └── DraggableMeasure (x N)
├── PivotBuilder                      # 피벗 빌더 (DnD 타겟)
│   ├── DroppableZone (행)            # @dnd-kit Droppable
│   ├── DroppableZone (열)
│   ├── DroppableZone (측정값)
│   ├── DroppableZone (필터)
│   ├── SwapButton (행↔열)
│   └── RunQueryButton
├── PivotTable                        # 결과 피벗 테이블
│   ├── DrilldownBreadcrumb           # 경로 표시
│   ├── PivotGrid                     # 피벗 셀 그리드
│   │   ├── HeaderCell
│   │   ├── DataCell (클릭 -> 드릴다운)
│   │   └── TotalCell
│   └── QueryInfo (시간, 행/열 수)
├── ChartSwitcher                     # 차트 전환
│   ├── shared/Chart/BarChart
│   ├── shared/Chart/LineChart
│   └── shared/Chart/PieChart
└── ExportButton                      # CSV 내보내기
```

---

## 5. K-AIR 전환 매핑

| K-AIR (data-platform-olap) | Canvas | 전환 노트 |
|----------------------------|--------|-----------|
| `PivotEditor.vue` | PivotBuilder + DimensionPalette | vue-draggable -> @dnd-kit |
| `PivotTable.vue` | PivotTable + PivotGrid | 셀 렌더링 최적화 필요 |
| `CubeModeler.vue` | DimensionPalette | 큐브 구조는 Vision API에서 제공 |
| `cubeStore.pivotConfig` | pivotConfigStore (Zustand) | rows/columns/measures/filters 동일 |
| 탭: pivot/natural/modeler/lineage | 별도 라우트 분리 | OLAP, NL2SQL, 온톨로지 각각 독립 |
| i18n (ko/en/de/es/ja) | i18n (ko/en만) | 불필요 언어 제거 |

---

## 6. 상태 관리

```typescript
// stores/pivotConfigStore.ts (Zustand)
// K-AIR cubeStore의 pivotConfig 대응

interface PivotConfig {
  cubeId: string | null;
  rows: Dimension[];
  columns: Dimension[];
  measures: Measure[];
  filters: OlapFilter[];
  drilldownPath: DrilldownStep[];
}

// 이 상태를 기반으로 OLAP 쿼리 자동 실행
// hooks/useOlapQuery.ts
function useOlapQuery(config: PivotConfig) {
  return useQuery({
    queryKey: ['olap', 'query', config],
    queryFn: () => olapApi.query(config),
    enabled: !!config.cubeId && config.measures.length > 0,
    staleTime: 10 * 60 * 1000,  // 10분 캐시
  });
}
```

---

## 7. API 연동

### 7.1 백엔드 엔드포인트

OLAP 피벗 UI는 Vision 서비스의 OLAP API를 사용한다.

| 기능 | Method | Path | 설명 |
|------|--------|------|------|
| 큐브 목록 | GET | `/api/v1/olap/cubes` | 사용 가능한 OLAP 큐브 목록 |
| 큐브 상세 | GET | `/api/v1/olap/cubes/{cubeId}` | 차원/측정값 메타데이터 |
| 피벗 쿼리 | POST | `/api/v1/olap/query` | 피벗 쿼리 실행 (rows/columns/measures/filters) |
| CSV 내보내기 | POST | `/api/v1/olap/export` | 쿼리 결과 CSV 다운로드 |

- **API 스펙**: Vision OLAP API (확정 시 경로 동기화 필요)
- **라우팅**: Core API Gateway를 통해 Vision 서비스로 프록시됨

> **백엔드 협의 필요**: 위 엔드포인트 목록은 프론트엔드 요구사항 기반 설계이다. Vision 서비스의 실제 OLAP API 스펙이 확정되면 경로/필드를 동기화해야 한다.

---

## 8. UX 상태 설계 (에러/빈 상태/로딩)

### 8.1 에러 상태

| 시나리오 | UI 표시 | 액션 |
|---------|---------|------|
| 페이지 로드 실패 | ErrorFallback (implementation-guide.md §1.2) | "다시 시도" 버튼 |
| 큐브 목록 조회 실패 | CubeSelector 영역 에러 + "다시 시도" | 캐시 무효화 |
| 피벗 쿼리 실패 | ResultArea에 에러 메시지 + 실패 쿼리 표시 | "쿼리 수정" 유도 |
| 드릴다운 실패 | 토스트 에러 + 이전 드릴다운 레벨 유지 | Breadcrumb에서 이전 레벨 클릭 |
| CSV 내보내기 실패 | 토스트 에러 | 재시도 |

### 8.2 빈 상태

| 시나리오 | UI 표시 |
|---------|---------|
| 큐브 미선택 | 중앙 안내: "분석할 큐브를 선택하세요" + CubeSelector 강조 |
| 측정값 미배치 | PivotBuilder 하단: "측정값을 1개 이상 배치한 후 쿼리를 실행하세요" |
| 쿼리 결과 0건 | ResultArea: "조건에 맞는 데이터가 없습니다. 필터를 확인하세요." |
| 차원 없는 큐브 | "(이 큐브에 사용 가능한 차원이 없습니다)" |

### 8.3 로딩 상태

| 시나리오 | UI 표시 |
|---------|---------|
| 큐브 목록 조회 | CubeSelector에 Skeleton 드롭다운 |
| 차원/측정값 팔레트 조회 | DimensionPalette에 Skeleton 칩 6개 |
| 피벗 쿼리 실행 | ResultArea에 PivotTableSkeleton (헤더 + 5행) + 쿼리 시간 카운터 |
| 드릴다운 재조회 | 현재 테이블 opacity 50% + 스피너 오버레이 |

---

## 9. 역할별 접근 제어 (RBAC)

### 9.1 기능별 역할 권한

| 기능 | 필요 권한 | admin | manager | attorney | analyst | engineer | staff | viewer |
|------|----------|:-----:|:-------:|:--------:|:-------:|:--------:|:-----:|:------:|
| 큐브 목록/상세 조회 | `olap:query` | O | O | O | O | O | O | O |
| 피벗 쿼리 실행 | `olap:query` | O | O | O | O | O | O | O |
| CSV 내보내기 | `olap:query` | O | O | O | O | O | O | O |
| 큐브 관리 (생성/수정/삭제) | `olap:manage` | O | X | X | X | X | X | X |

### 9.2 프론트엔드 가드

```typescript
// OLAP은 모든 역할이 접근 가능 (viewer 포함)하므로 페이지 가드가 필요 없음
// 큐브 관리 버튼만 admin에게 표시
const { hasPermission } = usePermission();

{hasPermission('olap:manage') && (
  <Button onClick={openCubeManager}>큐브 관리</Button>
)}
```

> **SSOT**: 권한 매트릭스는 `services/core/docs/07_security/auth-model.md` §2.3을 따른다.

---

## 결정 사항 (Decisions)

- @dnd-kit 사용 (vue-draggable 대체)
  - 근거: React 네이티브, 접근성, 경량
  - 대안: react-beautiful-dnd (유지보수 중단됨)

- OLAP 탭 분리 -> 별도 라우트
  - 근거: K-AIR는 4개 탭을 한 페이지에 넣어 초기 로딩 과중
  - Canvas: `/analysis/olap`, `/analysis/nl2sql`, `/data/ontology` 각각 별도 lazy load

## 금지됨 (Forbidden)

- 피벗 결과를 프론트엔드에서 집계 (반드시 Vision API에서 집계)
- 드릴다운 경로를 로컬에만 저장 (URL search params에 반영하여 공유 가능하게)

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.2 | Axiom Team | RBAC 역할별 접근 제어(§9) 추가 |
| 2026-02-20 | 1.1 | Axiom Team | API 연동(§7), UX 상태 설계(§8) 추가 |
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
