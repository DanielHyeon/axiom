# What-if 시나리오 빌더 UI

<!-- affects: frontend, api -->
<!-- requires-update: 02_api/api-contracts.md (Vision API) -->

## 이 문서가 답하는 질문

- What-if 시나리오 빌더의 화면 구성은 어떻게 되는가?
- 매개변수 슬라이더와 토네이도 차트는 어떻게 동작하는가?
- 시나리오 비교는 어떤 형태로 표시되는가?
- K-AIR에서 미구현이었던 이 기능을 어떻게 신규 설계하는가?

---

## 1. 기능 개요

What-if 시나리오 빌더는 **비용 배분율, 실행 계획의 변수를 조정하여 결과를 시뮬레이션**하는 도구이다. K-AIR의 data-platform-olap에서 "What-if 시뮬레이션"으로 계획되었으나 미구현 상태였으므로, Canvas에서 신규 설계한다.

---

## 2. 화면 와이어프레임

```
┌──────────────────────────────────────────────────────────────────────┐
│ 📊 What-if 시나리오 빌더                 케이스: 물류최적화 프로젝트  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────── 매개변수 패널 ──────────────────┐                │
│  │                                                  │                │
│  │  비용배분율 (%)                                   │                │
│  │  ◄──────────────●──────────────────────────► │                │
│  │  0%           42%                          100%  │                │
│  │                                                  │                │
│  │  자원 활용률 (%)                                  │                │
│  │  ◄────────────────●────────────────────────► │                │
│  │  0%              65%                       100%  │                │
│  │                                                  │                │
│  │  운영 비용 (억원)                                 │                │
│  │  ◄──●──────────────────────────────────────► │                │
│  │  0   15                                     200  │                │
│  │                                                  │                │
│  │  프로젝트 기간 (년)                                │                │
│  │  ◄──────●──────────────────────────────────► │                │
│  │  1      3                                    10  │                │
│  │                                                  │                │
│  │  [기본값 복원]  [시나리오 저장]  [분석 실행 →]    │                │
│  └──────────────────────────────────────────────────┘                │
│                                                                      │
│  ┌─────────── 결과 패널 ──────────────────────────────────────────┐ │
│  │                                                                 │ │
│  │  ┌──────────────────────┐  ┌──────────────────────────────┐   │ │
│  │  │ 결과 요약             │  │ 토네이도 차트 (민감도 분석)   │   │ │
│  │  │                       │  │                               │   │ │
│  │  │ 총 비용절감: 283억    │  │  배분율      ◄████████████► │   │ │
│  │  │  (기준 대비 ▲ 12%)   │  │  활용률      ◄█████████►    │   │ │
│  │  │                       │  │  운영비용    ◄██████►       │   │ │
│  │  │ 이해관계자 만족도:47% │  │  프로젝트기간◄████►         │   │ │
│  │  │  (기준 대비 ▲ 5%p)   │  │                               │   │ │
│  │  │                       │  │  ◄ 감소 영향  기준  증가 영향 ► │   │ │
│  │  │ 예상 소요기간: 2.8년  │  │                               │   │ │
│  │  └──────────────────────┘  └──────────────────────────────┘   │ │
│  │                                                                 │ │
│  │  ┌──────────────────────────────────────────────────────────┐ │ │
│  │  │ 시나리오 비교 테이블                                      │ │ │
│  │  │                                                           │ │ │
│  │  │           │ 기준 시나리오 │ 현재 조정  │ 낙관적    │ 비관적│ │ │
│  │  │ ──────────┼─────────────┼───────────┼──────────┼───────│ │ │
│  │  │ 배분율    │     35%      │    42%     │   55%     │   20% │ │ │
│  │  │ 활용률    │     55%      │    65%     │   80%     │   40% │ │ │
│  │  │ 총절감액  │    253억     │   283억    │   340억   │  180억│ │ │
│  │  │ 만족도    │     42%      │    47%     │   56%     │   30% │ │ │
│  │  │ 소요기간  │    3.2년     │   2.8년    │   2.0년   │  4.5년│ │ │
│  │  └──────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. 컴포넌트 분해

```
WhatIfPage
├── ScenarioPanel
│   ├── ParameterSlider (x N)
│   │   ├── shared/ui/Label
│   │   ├── Slider (Shadcn/ui Slider)
│   │   └── 현재값 표시
│   ├── ResetButton
│   ├── SaveScenarioButton
│   └── RunAnalysisButton
├── ResultSummary
│   ├── shared/ui/Card (x 결과 지표 수)
│   └── 변화량 표시 (▲/▼ + %)
├── TornadoChart
│   └── Recharts BarChart (가로 막대, 양방향)
└── ScenarioComparison
    └── shared/DataTable (시나리오 열 비교)
```

---

## 4. 토네이도 차트 상세

토네이도 차트는 **각 매개변수가 결과에 미치는 영향의 크기**를 시각화한다.

```
                     ◄── 감소 영향 ──┤── 기준 ──├── 증가 영향 ──►

  배분율 (%)    ████████████████████│▓▓▓▓▓▓▓▓│████████████████████
  활용률 (%)    ██████████████████  │▓▓▓▓▓▓▓▓│  ██████████████████
  운영비용 (억) ████████████        │▓▓▓▓▓▓▓▓│        ████████████
  프로젝트기간  ██████              │▓▓▓▓▓▓▓▓│              ██████

  범위: 각 변수를 +-20% 변동 시 결과 지표(총 비용절감액) 변화
  정렬: 영향도(impact) 내림차순
```

### 구현

```typescript
// Recharts 기반 토네이도 차트
// 각 막대는 [lowValue, highValue] 범위를 표현
// 기준선(baseValue)을 중심으로 양방향 표시

interface TornadoChartProps {
  data: SensitivityData[];    // Vision API 응답
  baseValue: number;           // 기준 결과값
  metric: string;              // "총 비용절감액"
  unit: string;                // "억원"
}
```

---

## 5. API 연동

### 5.1 백엔드 엔드포인트

What-if 빌더는 Vision 서비스의 What-if API를 사용한다. 모든 엔드포인트는 **케이스 스코프**이다.

| 단계 | Method | Path | 설명 |
|------|--------|------|------|
| 목록 조회 | GET | `/api/v1/cases/{caseId}/what-if` | 기존 시나리오 목록 |
| 시나리오 생성 | POST | `/api/v1/cases/{caseId}/what-if` | 새 시나리오 생성 (DRAFT) |
| 시나리오 수정 | PUT | `/api/v1/cases/{caseId}/what-if/{id}` | 매개변수 업데이트 |
| 계산 실행 | POST | `/api/v1/cases/{caseId}/what-if/{id}/compute` | 비동기 계산 (202 Accepted) |
| 상태 확인 | GET | `/api/v1/cases/{caseId}/what-if/{id}/status` | 계산 진행 상태 폴링 |
| 결과 조회 | GET | `/api/v1/cases/{caseId}/what-if/{id}/result` | 계산 완료 결과 |
| 민감도 분석 | POST | `/api/v1/cases/{caseId}/what-if/{id}/sensitivity` | 토네이도 차트 데이터 |
| 시나리오 비교 | GET | `/api/v1/cases/{caseId}/what-if/compare?ids=...` | 다중 시나리오 비교 |

- **API 스펙**: Vision [what-if-api.md](../../../services/vision/docs/02_api/what-if-api.md)
- **라우팅**: Core API Gateway를 통해 Vision 서비스로 프록시됨
- **비동기 계산**: `/compute`는 202를 반환하므로, `/status`를 폴링(2초 간격)하여 완료 확인 필요

### 5.2 시나리오 상태 라이프사이클

```
DRAFT → READY → COMPUTING → COMPLETED
                     │
                     └──→ FAILED
```

| 상태 | UI 표시 |
|------|---------|
| `DRAFT` | 슬라이더 활성, "분석 실행" 버튼 활성 |
| `COMPUTING` | 프로그레스 인디케이터, 버튼 비활성 |
| `COMPLETED` | 결과 패널 표시 (요약 + 토네이도 + 비교) |
| `FAILED` | 에러 메시지 + "재시도" 버튼 |

### 5.3 사용자 인터랙션 흐름

```
1. 페이지 진입 (caseId = route param /cases/:caseId/scenarios)
   │
   ├── GET /api/v1/cases/{caseId}/what-if (기존 시나리오 목록)
   └── 시나리오 선택 또는 "새 시나리오" → POST /api/v1/cases/{caseId}/what-if
       │
2. 슬라이더 조정 (매개변수 설정)
   │
   ├── 디바운스 300ms, 로컬 상태만 업데이트 (서버 호출 안함)
   └── "기본값 복원" 버튼으로 초기화 가능
       │
3. "분석 실행" 클릭
   │
   ├── Step 1: POST /api/v1/cases/{caseId}/what-if/{id}/compute → 202 Accepted
   ├── Step 2: 폴링 GET /api/v1/cases/{caseId}/what-if/{id}/status (2초 간격)
   │   └── status가 COMPLETED 또는 FAILED일 때 폴링 중단
   ├── Step 3: GET /api/v1/cases/{caseId}/what-if/{id}/result (결과 조회)
   └── Step 4: POST /api/v1/cases/{caseId}/what-if/{id}/sensitivity (토네이도)
       └── 결과 요약 + 토네이도 차트 렌더링
       │
4. "시나리오 저장" (매개변수 변경 시)
   │
   └── PUT /api/v1/cases/{caseId}/what-if/{id}
       │
5. 시나리오 비교 (2개 이상 COMPLETED 시나리오 선택)
   │
   └── GET /api/v1/cases/{caseId}/what-if/compare?ids=id1,id2,...
       └── 비교 테이블 렌더링
```

### 5.4 타입 정의

```typescript
// features/what-if/types/whatif.ts

/** 민감도 분석 데이터 — Vision API sensitivity 응답과 일치 */
interface SensitivityData {
  parameter: string;
  parameter_label: string;
  base_value: number;
  high_value: number;
  low_value: number;
  impact: number;
  high_pct_change: number;
  low_pct_change: number;
}

/** 시나리오 상태 */
type ScenarioStatus = 'DRAFT' | 'READY' | 'COMPUTING' | 'COMPLETED' | 'FAILED';

/** 시나리오 유형 */
type ScenarioType = 'OPTIMISTIC' | 'PESSIMISTIC' | 'BASE' | 'CUSTOM';
```

---

## 6. UX 상태 설계 (에러/빈 상태/로딩)

### 6.1 에러 상태

| 시나리오 | UI 표시 | 액션 |
|---------|---------|------|
| 페이지 로드 실패 | ErrorFallback (implementation-guide.md §1.2) | "다시 시도" 버튼 |
| 계산 실패 (status: FAILED) | ResultPanel에 에러 메시지 + "재시도" 버튼 | RunAnalysisButton 다시 활성화 |
| 폴링 타임아웃 (5분 초과) | "계산이 예상보다 오래 걸리고 있습니다." + "계속 대기" / "취소" 선택 | 폴링 재시작 또는 DRAFT 복귀 |
| 시나리오 저장 실패 | 토스트 에러 "시나리오를 저장하지 못했습니다." | 재시도 유도 |
| 민감도 분석 실패 | 토네이도 차트 영역에 "민감도 분석에 실패했습니다." + "재시도" | sensitivity API 재호출 |

### 6.2 빈 상태

| 시나리오 | UI 표시 |
|---------|---------|
| 시나리오 없음 (첫 진입) | EmptyState: 📊 아이콘 + "What-if 시나리오를 만들어 보세요" + [새 시나리오 만들기] 버튼 |
| 분석 실행 전 (결과 없음) | ResultPanel 자리: "슬라이더를 조정한 후 '분석 실행'을 클릭하세요" |
| 비교 가능 시나리오 없음 | "비교하려면 2개 이상의 완료된 시나리오가 필요합니다." |

### 6.3 로딩 상태

| 시나리오 | UI 표시 |
|---------|---------|
| 기존 시나리오 목록 조회 | ScenarioListSkeleton (카드 3개) |
| 계산 진행 중 (COMPUTING) | ProgressIndicator: 스피너 + "분석 진행 중..." + 경과 시간 표시 |
| 결과 조회 중 | ResultSkeleton: 요약 카드 3개 + 토네이도 영역 Skeleton |
| 시나리오 비교 조회 중 | ComparisonTableSkeleton |

---

## 7. 역할별 접근 제어 (RBAC)

### 7.1 기능별 역할 권한

What-if 빌더는 케이스 스코프 기능이므로, 시스템 역할과 케이스 역할이 모두 적용된다.

**시스템 역할 기반**:

| 기능 | 필요 권한 | admin | manager | attorney | analyst | engineer | staff | viewer |
|------|----------|:-----:|:-------:|:--------:|:-------:|:--------:|:-----:|:------:|
| 시나리오 목록/결과 조회 | `case:read` | O | O | O | O | O | O | O |
| 시나리오 생성/수정 | `case:write` | O | O | O | X | X | X | X |
| 분석 실행 (compute) | `case:write` | O | O | O | O* | X | X | X |
| 시나리오 삭제 | `case:write` | O | O | O | X | X | X | X |
| 시나리오 비교 | `case:read` | O | O | O | O | O | O | O |

`*` analyst는 담당 케이스(case_roles: trustee)에서만 분석 실행 가능

**케이스 역할 기반** (시스템 역할과 AND 조건):

| 케이스 역할 | 시나리오 조회 | 시나리오 생성/수정 | 분석 실행 |
|------------|:----------:|:---------------:|:--------:|
| trustee | O | O | O |
| reviewer | O | X | X |
| viewer | O | X | X |

### 7.2 프론트엔드 가드

```typescript
// RunAnalysisButton — 권한이 없으면 비활성화
const { hasPermission } = usePermission();
const canRunAnalysis = hasPermission('case:write') && caseRole !== 'viewer';

<Button disabled={!canRunAnalysis} onClick={runAnalysis}>
  분석 실행
</Button>
```

> **SSOT**: 시스템 역할 권한은 `services/core/docs/07_security/auth-model.md` §2.3, 케이스 역할은 §2.2를 따른다.

---

## 8. 결정 사항 (Decisions)

- 슬라이더 조정은 서버 호출 없이 로컬 미리보기, "분석 실행" 시 서버 호출
  - 근거: 실시간 서버 호출은 비용 과다, 사용자가 여러 변수를 동시에 조정할 수 있어야 함

- 비동기 계산 + 폴링 패턴 (compute → status 폴링 → result 조회)
  - 근거: Vision API의 compute 엔드포인트가 비동기(202)이므로, 프론트엔드에서 상태 폴링 필요
  - 폴링 간격: 2초, 최대 5분 타임아웃 후 에러 표시

- 토네이도 차트는 Recharts 가로 BarChart로 구현
  - 근거: 전용 토네이도 라이브러리보다 Recharts 활용이 유지보수 용이

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 2.1 | Axiom Team | RBAC 역할별 접근 제어(§7) 추가 |
| 2026-02-20 | 2.0 | Axiom Team | API 연동(§5) 전면 개편 (케이스 스코프, 비동기 계산, 타입 정의), UX 상태 설계(§6) 추가 |
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 (K-AIR 미구현 -> 신규 설계) |
