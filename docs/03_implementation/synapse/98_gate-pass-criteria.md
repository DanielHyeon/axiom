# SYNAPSE Gate 통과 기준

## Gate S0: 설계 정합
- 00~99 구현 계획 문서 존재
- 4-Layer 온톨로지/그래프 모델/프로세스 마이닝 경계 충돌 0건
- `99_traceability-matrix.md` 반영율 100%

## Gate S1: API/파이프라인
- ontology/graph/extraction/event-log/process-mining/schema-edit API 계약 테스트 100%
- HITL 임계값(자동반영/검토대기/수동) 분기 정확성 검증 완료
- 재시도/멱등성/보상 API 회귀 0건

## Gate S2: 그래프/마이닝
- Neo4j bootstrap 인덱스/제약조건 검증 완료
- process discovery + conformance 결과 저장 정합성 통과
- 대량 이벤트 ingest 시 누락/중복 허용치 이내

## Gate S3: 보안/운영
- case_id/tenant_id 누락 조회 차단 100%
- Critical/High 취약점 0건
- 배포 후 헬스체크/모니터링/알람 룰 정상 작동
