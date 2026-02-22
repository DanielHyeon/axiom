# Program 기능 성숙도 체크리스트 (10)

## 1. 목적
- K-AIR 기준 미구현/저성숙 6개 항목을 Axiom 프로그램 기준으로 동일 형식으로 관리한다.
- 각 항목을 `설계 반영 완료 -> 구현 착수 -> 구현 완료` 3단계로 추적한다.

## 2. 대상 기능
1. What-if 시뮬레이션
2. 4-Layer 온톨로지 (R->P->M->KPI)
3. 비정형 -> 온톨로지 추출
4. See-Why 근본원인 분석
5. Watch Agent
6. 이벤트 감지(CEP)

## 3. 단계 정의
- `D1 설계 반영 완료`: 아키텍처/API/데이터/보안/운영 문서와 추적 매트릭스가 연결됨
- `D2 구현 착수`: 스프린트 티켓 배정 + 담당자 + 의존성 + 테스트 계획이 확정됨
- `D3 구현 완료`: Gate 통과 + 계약 테스트 + 운영 지표 검증이 완료됨

## 4. 항목별 체크리스트 (2026-02-22 기준)

| 기능 | D1 설계 반영 | D2 구현 착수 | D3 구현 완료 | 현재 판정 | 담당자 | ETA | 최근 업데이트 | 핵심 리스크 |
|---|---|---|---|---|---|---|---|---|
| What-if 시뮬레이션 | ✅ | ✅ | ⏳ | D2 진행 (full-spec 재검증 필요) | `backend-developer`, `api-developer` | Re-baseline 필요 | 2026-02-22 | Vision 런타임이 mock/in-memory 중심으로 운영 증적 불충분 |
| 4-Layer 온톨로지 | ✅ | ✅ | ✅ | D3 완료 (Sprint 3) | `backend-developer`, `api-developer` | Sprint 3 Exit | 2026-02-21 | 통합 검증 완료 |
| 비정형->온톨로지 추출 | ✅ | ✅ | ✅ | D3 완료 (Sprint 3) | `backend-developer`, `code-inspector-tester` | Sprint 3 Exit | 2026-02-21 | 승인 파이프라인 연동 완료 |
| See-Why 근본원인 분석 | ✅ | ✅ | ⏳ | D2 진행 (최소 API 구현 완료, 확장 API 잔여) | `backend-developer`, `api-developer` | Sprint 10 재기준화 | 2026-02-22 | causal-timeline/impact/graph/bottleneck 및 Synapse 연동 미구현 |
| Watch Agent | ✅ | ✅ | ⏳ | D2 진행 (API 구현 + Canvas 인증 1차 반영, 운영 재검증 필요) | `backend-developer`, `code-inspector-tester` | Re-baseline 필요 | 2026-02-22 | refresh 만료/회전 E2E 및 운영 SLA 증적 보강 필요 |
| 이벤트 감지(CEP) | ✅ | ✅ | ⏳ | D2 진행 (재검증 필요) | `backend-developer`, `code-reviewer` | Re-baseline 필요 | 2026-02-22 | Outbox 이후 Redis Streams 운영 증적 불충분 |

## 5. 근거 문서 맵

### 5.1 What-if
- 설계: `services/vision/docs/01_architecture/what-if-engine.md`, `services/vision/docs/02_api/what-if-api.md`
- 계획: `docs/implementation-plans/program/06_sprint5-execution-tickets.md`

### 5.2 4-Layer 온톨로지
- 설계: `services/synapse/docs/99_decisions/ADR-002-4layer-ontology.md`, `services/synapse/docs/01_architecture/ontology-4layer.md`
- 계획: `docs/implementation-plans/program/04_sprint3-execution-tickets.md`, `docs/implementation-plans/synapse/98_gate-pass-criteria.md`

### 5.3 비정형->온톨로지 추출
- 설계: `services/synapse/docs/01_architecture/extraction-pipeline.md`, `services/synapse/docs/02_api/extraction-api.md`
- 계획: `docs/implementation-plans/program/04_sprint3-execution-tickets.md`, `docs/implementation-plans/synapse/98_gate-pass-criteria.md`

### 5.4 See-Why
- 설계: `services/vision/docs/01_architecture/root-cause-engine.md`, `services/vision/docs/02_api/root-cause-api.md`
- 계획: `docs/implementation-plans/program/06_sprint5-execution-tickets.md` (Phase 4 이관 명시)

### 5.5 Watch Agent
- 설계: `services/core/docs/01_architecture/event-driven.md`, `services/core/docs/02_api/watch-api.md`
- 계획: `docs/implementation-plans/core/02_api-implementation-plan.md`, `docs/implementation-plans/core/98_gate-pass-criteria.md`

### 5.6 이벤트 감지(CEP)
- 설계: `services/core/docs/99_decisions/ADR-004-redis-streams-event-bus.md`, `services/core/docs/01_architecture/event-driven.md`
- 계획: `docs/implementation-plans/program/03_sprint2-execution-tickets.md`

## 6. 실행 티켓 세트 (추가)

| Ticket ID | 기능 | 단계 | 작업 | 선행 의존 | 완료 기준 |
|---|---|---|---|---|---|
| FM-001 | What-if | D3 | Vision Gate V1/V2 잔여 항목 완료 | S5-PGM-005 | 계약 테스트/성능 기준 통과 |
| FM-002 | 4-Layer 온톨로지 | D3 | Synapse Gate S1/S2 잔여 항목 완료 | S3-PGM-006 | 계층 경계 충돌 0건 |
| FM-003 | 비정형->온톨로지 | D3 | HITL 임계값/검토대기열/커밋 흐름 검증 완료 | S3-PGM-007 | 자동반영/검토대기 분기 정확성 통과 |
| FM-004 | See-Why | D2 | Phase 4 착수 패키지 작성(데이터 100건+, 학습/평가 계획) | S7-PGM-007 | Phase 4 킥오프 승인 |
| FM-005 | Watch Agent | D2 | Early Warning 폐루프 SLA 계측 재검증 | S7-PGM-005 | detect->resolve 지표 대시보드 증적 재확인 |
| FM-006 | 이벤트 감지(CEP) | D2 | CEP 오탐률/지연 지표 재검증 | S7-PGM-006 | 이벤트 지연/오탐률 목표 증적 재확인 |

## 6.1 운영 대시보드 갱신 규칙
- 주기: 각 Sprint 주간 리뷰(최소 주 1회)
- 필수 갱신 항목: `현재 판정`, `ETA`, `최근 업데이트`, `핵심 리스크`
- 상태 전이 규칙:
  - `⏳` -> `✅` 전이는 해당 Sprint Exit Review에서만 확정
  - `✅` -> `⏳` 롤백은 결함/리스크 재개 시 근거 티켓을 함께 기록

## 7. 통과 증적 규칙
- D1: 설계 문서 + `99_traceability-matrix.md` 반영율 100%
- D2: 스프린트 티켓 + 책임자 + 테스트 케이스 링크
- D3: `98_gate-pass-criteria.md` 체크 증적 + 운영 지표 캡처 + 회귀 테스트 결과

## 8. Generate -> Operate -> Learn 플라이휠 제품 KPI
"자율 에이전트 모델 진화 루프"의 실효성을 정량적으로 추적하기 위해 전체 프로그램에 다음 핵심 성과 지표(KPI)를 적용한다. 운영 대시보드를 통해 주기적으로 모니터링한다.

1. **학습 속도 (Learning Velocity)**
   - **정의**: 신규 도메인/패턴(미등록 이벤트, 누락된 정책 등)이 최초 발견된 시점부터 온톨로지 모델 및 에이전트 로직으로 정식 반영/학습되기까지의 "리드타임(Lead Time)".
   - **목표**: 지속적 단축 (이상 징후 인지 -> 반영 자동화 파이프라인 최적화).
2. **인간 개입 승인율 개선 (HITL Approval Rate)**
   - **정의**: 에이전트가 제안한 추출 결과, 대응 방안 등에 대해 코 파일럿 모드에서 인간 전문가(HITL)가 거부권 없이 "자동 승인" 처리한 비율.
   - **목표**: 모델 진화와 함께 점진적 상승 (초기 20% -> Phase 4 도달 시 90% 이상).
3. **오탐 및 누락 감소율 (False Positive / Omission Reduction)**
   - **정의**: Watch Agent 감지 및 Self-Verification 하네스에서 "거짓 경보(False Positives)" 및 "탐지 실패(Omissions)"가 발생하는 빈도의 하락 곡선.
   - **목표**: 릴리스/스프린트가 경과할수록 노이즈 최소화 트렌드 달성.
