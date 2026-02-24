# Sprint 8 실행 티켓 보드 (Program)

## 범위
- 목표: Planned API의 P0/P1 구간 구현 착수 및 계약-런타임 정합 복구
- 전제: Sprint 7 문서 재정렬 완료

| Ticket ID | 프로젝트 | 작업 | 선행 의존 | 예상 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| S8-PGM-001 | Program | Sprint 8 킥오프 및 API 정합 범위 확정 | S7-PGM-008 | 0.5d | code-implementation-planner | 범위/우선순위 승인 |
| S8-PGM-002 | Core | P0 Watch Alerts API 구현 | S8-PGM-001 | 2d | backend-developer, api-developer | `/watches/alerts*` 동작 + 계약테스트 통과 |
| S8-PGM-003 | Core | P0 Watch Subscriptions/Rules API 구현 | S8-PGM-002 | 2d | backend-developer, code-security-auditor | 구독 CRUD + rules API 동작 |
| S8-PGM-004 | Core | P0 Process Lifecycle 보강 (`/initiate/status/workitems/approve-hitl/rework`) | S8-PGM-001 | 2d | backend-developer | 상태전이 회귀 테스트 통과 |
| S8-PGM-005 | Synapse | P1 Event-Log API 1차 구현 | S8-PGM-001 | 3d | backend-developer, code-inspector-tester | ingest/list/detail/preview/statistics 동작 |
| S8-PGM-006 | Synapse | P1 Extraction API 1차 구현 | S8-PGM-005 | 3d | backend-developer, api-developer | extraction/status/result + HITL 큐 동작 |
| S8-PGM-007 | Oracle | P1 Meta API 1차 구현 | S8-PGM-001 | 2d | backend-developer, api-developer | `/text2sql/meta/*` 동작 |
| S8-PGM-008 | Core | P1 Gateway event-log/process-mining 프록시 구현 | S8-PGM-005,S8-PGM-006 | 2d | backend-developer | Core 경유 라우팅/에러매핑 동작 |
| S8-PGM-009 | Program | 문서 상태(Implemented/Partial/Planned) 재동기화 및 Sprint 8 Exit 리뷰 | S8-PGM-002~008 | 1d | code-reviewer, code-documenter | 문서-코드 불일치 고위험 항목 0건 |

## Sprint 8 Exit Criteria
- [ ] Core Watch API 핵심 경로(`/alerts`, `/alerts/{id}/acknowledge`, `/alerts/read-all`)가 Canvas에서 정상 호출됨
- [ ] Core Process 필수 경로(`/initiate`, `/status`, `/workitems`, `/approve-hitl`, `/rework`) 구현 완료
- [ ] Synapse Event-Log/Extraction API 1차 구현 및 계약 테스트 통과
- [ ] Oracle Meta API 1차 구현 완료
- [ ] Core Gateway event-log/process-mining 프록시 동작 확인
- [ ] 관련 API 문서의 상태 태그/근거 컬럼 최신화

## 2026-02-22 상태 메모 (보고서 기준)

- 참조 보고서: `docs/04_status/full-spec-gap-analysis.md`
- 해석 기준: Sprint 8의 `API 복구` 목표와 `full spec` 목표를 분리해 관리한다.

### 1차 API 복구 기준
- [x] Core Watch API 핵심 경로 구현
- [x] Core Process 필수 경로 구현
- [x] Synapse Event-Log/Extraction API 구현
- [x] Oracle Meta API 구현
- [x] Core Gateway event-log/process-mining 프록시 구현

### Full Spec 잔여(후속 스프린트 이관)
- [ ] Canvas 실제 인증/실연동 기준의 Watch 호출 검증
- [ ] Vision Root-Cause API 구현
- [ ] Oracle/Vision/Core Agent mock/in-memory 경로 실연동 전환
- [ ] Self-Verification/4-Source Lineage/Domain Contract Enforcement 구현
- [ ] SSOT vs Compose/K8s 완전 동기화
