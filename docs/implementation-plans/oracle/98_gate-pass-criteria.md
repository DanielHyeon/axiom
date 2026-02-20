# ORACLE Gate 통과 기준

## Gate O0: 설계 정합
- 00~99 구현 계획 문서 존재
- Oracle↔Synapse 경계(직접 그래프 저장소 접근 금지) 위반 0건
- `99_traceability-matrix.md` 반영율 100%

## Gate O1: NL2SQL/API
- text2sql/meta/feedback/events API 계약 테스트 100% 통과
- SQL Guard 규칙(SELECT-only/LIMIT/JOIN depth/subquery depth) 위반 SQL 실행 0건
- 오류 응답 표준(code/message/details/requestId) 준수율 100%

## Gate O2: 품질게이트/캐시
- 품질게이트 임계값 정책대로 APPROVE/PENDING/REJECT 분류 재현
- 캐시 반영 실패 시 원요청 성공 경로에 영향 없음
- Value Mapping 정합성(중복/충돌) 오류율 허용치 이내

## Gate O3: 보안/운영
- 테넌트 헤더/JWT 기반 격리 우회 불가
- 민감 컬럼 마스킹/row limit/테이블 ACL 정책 검증 완료
- 부하 시 p95 응답시간, 에러율, 비용 지표 목표 충족
