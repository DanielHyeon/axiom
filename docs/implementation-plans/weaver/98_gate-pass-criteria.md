# WEAVER Gate 통과 기준

## Gate W0: 설계 정합
- 00~99 구현 계획 문서 존재
- Adapter 패턴/Metadata 서비스 경계 위반 0건
- `99_traceability-matrix.md` 반영율 100%
- `docs/architecture-semantic-layer.md`와 Weaver 책임 경계 정합성 확인
- `docs/legacy-data-isolation-policy.md` 위반(원본 스키마 직접 변경 경로) 0건

## Gate W1: API/연결
- datasource/metadata/catalog/query API 계약 테스트 100%
- 데이터소스 연결/스키마 추출/동기화 실패 복구 시나리오 통과
- 마이그레이션(from K-AIR) 단계별 완료 기준 검증
- API 문서 상태 태깅(Implemented/Experimental/Planned)과 실제 런타임 상태 불일치 0건

## Gate W2: 메타데이터/그래프
- Neo4j schema v2 제약/인덱스/소유권 규칙 검증 완료
- 메타데이터 전파 지연/누락 허용치 이내
- LLM metadata enrichment 품질 기준 통과

## Gate W3: 보안/운영
- 연결정보 암호화/비밀관리/접근통제 검증 완료
- Critical/High 취약점 0건
- 운영 모니터링(동기화 실패율, 지연, 재시도) 정상
