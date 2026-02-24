# ORACLE Sprint 2 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| ORA-S2-001 | text2sql API 계약 기반 요청/응답 검증기 구현 | services/oracle/docs/02_api/text2sql-api.md | ORA-S1-006 | 1d | api-developer | 계약 위반 0건 |
| ORA-S2-002 | Synapse 연동 어댑터(검색/캐시반영) 구현 계획 확정 | services/oracle/docs/03_backend/service-structure.md | ORA-S2-001 | 1d | backend-developer | 연동 실패/재시도 정책 정의 |
| ORA-S2-003 | SQL Guard/SQL 실행 경계 테스트 세트 구현 | services/oracle/docs/01_architecture/sql-guard.md | ORA-S2-001 | 1d | code-inspector-tester | 금지 SQL 실행 0건 |
| ORA-S2-004 | 보안 정책(마스킹/ACL/row limit) 검증 자동화 | services/oracle/docs/07_security/sql-safety.md | ORA-S2-003 | 1d | code-security-auditor | 정책 누락 0건 |
| ORA-S2-005 | 품질게이트/캐시 파이프라인 진입 준비 | services/oracle/docs/03_backend/cache-system.md | ORA-S2-002 | 0.5d | backend-developer | Gate O1 사전요건 충족 |
| ORA-S2-006 | Sprint2 결과 문서화 및 O1 사전점검 | docs/03_implementation/oracle/98_gate-pass-criteria.md | ORA-S2-004,ORA-S2-005 | 0.5d | code-reviewer, code-documenter | O1 체크 통과 |
