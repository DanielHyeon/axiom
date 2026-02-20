# VISION Sprint 1 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| VIS-S1-001 | 모듈러 모놀리스 경계(ADR-005) 고정 | services/vision/docs/99_decisions/ADR-005-modular-monolith-over-split-services.md | - | 0.5d | code-implementation-planner | 엔진 경계/책임표 승인 |
| VIS-S1-002 | analytics/olap/what-if API 계약 점검 (root-cause 제외) | services/vision/docs/02_api/analytics-api.md | VIS-S1-001 | 1d | api-developer | 계약 불일치 0건 |
| VIS-S1-003 | ETL/MV 운영 책임 분리 기준 확정 | services/vision/docs/03_backend/etl-pipeline.md | VIS-S1-001 | 0.5d | backend-developer | 배치/온라인 경계 정의 |
| VIS-S1-004 | 데이터 접근 보안 체크리스트 확정 | services/vision/docs/07_security/data-access.md | VIS-S1-002 | 0.5d | code-security-auditor | 접근권한 점검 항목 완료 |
| VIS-S1-005 | 문서/추적 매트릭스 동기화 | docs/implementation-plans/vision/* | VIS-S1-002,VIS-S1-004 | 0.5d | code-documenter | 추적 누락 0건 |
