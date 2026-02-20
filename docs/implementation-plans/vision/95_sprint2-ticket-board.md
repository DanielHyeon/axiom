# VISION Sprint 2 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| VIS-S2-001 | analytics/olap API 계약 테스트 구현 | services/vision/docs/02_api/analytics-api.md | VIS-S1-005 | 1d | api-developer | 계약 테스트 통과 |
| VIS-S2-002 | ETL 파이프라인/배치 경계 구현 점검 | services/vision/docs/03_backend/etl-pipeline.md | VIS-S2-001 | 1d | backend-developer | ETL 경계 위반 0건 |
| VIS-S2-003 | what-if 비동기 실행 정책 확정 (root-cause는 Phase 4) | services/vision/docs/01_architecture/what-if-engine.md | VIS-S2-001 | 0.5d | backend-developer | 타임아웃/취소 정책 합의 |
| VIS-S2-004 | 데이터 접근 보안 테스트 자동화 | services/vision/docs/07_security/data-access.md | VIS-S2-001 | 0.5d | code-security-auditor | 권한 우회 불가 |
| VIS-S2-005 | Sprint2 결과 문서화 및 V1 사전점검 | docs/implementation-plans/vision/98_gate-pass-criteria.md | VIS-S2-003,VIS-S2-004 | 0.5d | code-reviewer, code-documenter | V1 선행 항목 통과 |
