# CORE Sprint 2 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| CORE-S2-001 | Process API 구현/상태전이 검증 강화 | services/core/docs/02_api/process-api.md | CORE-S1-006 | 1.5d | backend-developer | 상태전이 회귀 0건 |
| CORE-S2-002 | Worker 시스템/트랜잭션 경계 구현 점검 | services/core/docs/03_backend/worker-system.md | CORE-S2-001 | 1d | backend-developer | 보상/재시도 시나리오 통과 |
| CORE-S2-003 | Outbox->Redis Streams 멱등성 테스트 구현 | services/core/docs/06_data/event-outbox.md | CORE-S2-002 | 1d | code-inspector-tester | 중복/유실 허용치 이내 |
| CORE-S2-004 | 인증/격리 보안 검증 자동화 | services/core/docs/07_security/auth-model.md | CORE-S2-001 | 1d | code-security-auditor | 권한/테넌트 우회 불가 |
| CORE-S2-005 | 운영 관측/성능 지표 대시보드 기준 고정 | services/core/docs/08_operations/performance-monitoring.md | CORE-S2-003 | 0.5d | backend-developer | 핵심 SLI/SLO 정의 |
| CORE-S2-006 | Sprint2 결과 문서 및 Gate C1/C2 사전점검 | docs/03_implementation/core/98_gate-pass-criteria.md | CORE-S2-004,CORE-S2-005 | 0.5d | code-reviewer, code-documenter | C1/C2 체크 통과 |
