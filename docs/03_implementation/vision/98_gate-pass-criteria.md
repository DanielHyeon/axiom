# VISION Gate 통과 기준

## Gate V0: 설계 정합
- 00~99 구현 계획 문서 존재
- ADR-005(모듈러 모놀리스) 경계 위반(import 순환/엔진 직접결합) 0건
- `99_traceability-matrix.md` 반영율 100%

## Gate V1: API/엔진
- analytics/olap/what-if API 계약 테스트 100% (root-cause 제외)
- OLAP 쿼리 생성 정확성 및 what-if solver 결과 일관성 검증
- 비동기 작업 타임아웃/취소/재시도 시나리오 통과

## Gate V2: 데이터/LLM
- 큐브 정의/ETL/MV 갱신 경로 정합성 통과
- NL-to-pivot 구조화 출력 검증 실패율 목표치 이내
- 분석 설명 필드(근거/요약) 최소 품질 기준 충족

## Gate V3: 보안/운영
- 데이터 접근권한/케이스 격리 검증 완료
- Critical/High 취약점 0건
- 배포/관측/복구 절차 검증 완료
