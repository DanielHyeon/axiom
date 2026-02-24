# SYNAPSE 02_api API 계약 구현 계획

## 1. 문서 목적
- synapse 프로젝트의 02_api 설계 문서를 실제 구현 백로그로 변환한다.
- 단계별 책임 에이전트와 통과 기준을 명확히 정의한다.

## 2. 참조 설계 문서
- services/synapse/docs/02_api/event-log-api.md
- services/synapse/docs/02_api/extraction-api.md
- services/synapse/docs/02_api/graph-api.md
- services/synapse/docs/02_api/ontology-api.md
- services/synapse/docs/02_api/process-mining-api.md
- services/synapse/docs/02_api/schema-edit-api.md

## 3. 에이전트 운영
- 주관: api-developer | 협업: backend-developer, code-security-auditor, code-documenter
- 공통 점검: code-inspector-tester(테스트 완결성), code-standards-enforcer(품질게이트), code-documenter(문서 동기화)

## 4. 구현 작업 패키지
1. 엔드포인트별 Request/Response/Error 계약 확정(OpenAPI 우선)
2. 인증/인가/권한 매트릭스와 상태코드 정책 확정
3. Idempotency, Pagination, Rate-limit, Versioning 정책 반영
4. 계약 테스트(consumer/provider)와 회귀 테스트 세트 설계
5. SDK/클라이언트(BFF 포함) 영향 분석 및 변경 순서 확정

## 5. 통과 기준 (Gate 02)
- OpenAPI/계약 문서와 구현 파라미터 불일치 0건
- 4xx/5xx 에러 코드 표준화 완료
- 권한 누락 엔드포인트 0건

## 6. 산출물
- 구현 PR(코드 + 테스트 + 문서)
- 변경 영향 리포트(호환성/성능/보안)
- 운영 체크리스트 업데이트(필요 시)
