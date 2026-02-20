# Legacy Data Isolation Policy

## 1. 정책 목적
- 레거시 시스템 안정성과 보안 신뢰를 보장하면서 AI/분석 기능을 도입한다.

## 2. 강제 정책
1. Schema Invariant
- 플랫폼은 레거시 원본 DB의 스키마를 직접 변경하지 않는다.

2. Read-only First
- 레거시 원본 DB 접근은 기본적으로 읽기 전용 계정/세션을 사용한다.

3. Controlled Write Path
- 데이터 쓰기는 플랫폼 전용 저장소에서만 허용한다.
- 허용 저장소: Weaver 스냅샷/메타그래프, Synapse 온톨로지 저장소, Vision Materialized View/ETL 결과, Oracle 캐시

4. API-mediated Change
- 업무 변경은 원본 DB 직접 쓰기가 아니라 플랫폼 API/이벤트 경로를 통해 수행한다.

## 3. 준수 검증
- 아키텍처 리뷰 시 "원본 직접 수정 경로" 0건
- 보안 리뷰 시 read-only 계정/권한 검증 100%
- Gate 통과 시 정책 위반 티켓 0건

## 4. 예외 처리
- 법규/감사/운영상 긴급 변경이 필요한 경우, CAB 승인 + 변경 로그 + 롤백 계획이 있어야 한다.

## 5. 참조 문서
- `docs/architecture-semantic-layer.md`
- `services/weaver/docs/01_architecture/data-fabric.md`
- `services/weaver/docs/01_architecture/fabric-snapshot.md`
- `services/synapse/docs/08_operations/migration-from-kair.md`
