# ORACLE Sprint 1 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| ORA-S1-001 | Oracle↔Synapse 경계 규칙 고정 | services/oracle/docs/01_architecture/architecture-overview.md | - | 0.5d | code-implementation-planner | 직접 그래프 접근 금지 규칙 명문화 |
| ORA-S1-002 | text2sql/meta/feedback API 계약 고정 | services/oracle/docs/02_api/text2sql-api.md | ORA-S1-001 | 1d | api-developer | 계약 변경 잔여 이슈 0건 |
| ORA-S1-003 | SQL 안전성 정책의 구현 체크포인트 고정 | services/oracle/docs/07_security/sql-safety.md | ORA-S1-002 | 0.5d | code-security-auditor | Guard/Masking/ACL 검증 항목 정의 |
| ORA-S1-004 | Synapse 연동 어댑터 인터페이스 정의 | services/oracle/docs/03_backend/service-structure.md | ORA-S1-001 | 0.5d | backend-developer | 어댑터 I/F 명세 완료 |
| ORA-S1-005 | Sprint1 Gate O0/O1 사전점검 | docs/implementation-plans/oracle/98_gate-pass-criteria.md | ORA-S1-002,ORA-S1-003,ORA-S1-004 | 0.5d | code-reviewer | O0/O1 리스크 목록 정리 |
| ORA-S1-006 | 문서/추적 매트릭스 동기화 | docs/implementation-plans/oracle/* | ORA-S1-005 | 0.5d | code-documenter | 추적 매트릭스 누락 0건 |

