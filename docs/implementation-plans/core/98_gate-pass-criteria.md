# CORE Gate 통과 기준

## Gate C0: 설계 정합
- 00~99 구현 계획 문서 존재
- `99_traceability-matrix.md`의 모든 설계 문서가 `반영` 상태
- 서비스 경계(Core가 소유한 인증/프로세스/이벤트 책임) 충돌 0건

## Gate C1: 기능/API
- `02_api` 계약 테스트 통과율 100%
- 프로세스 상태 전이(TODO→IN_PROGRESS→SUBMITTED→DONE/REWORK/CANCELLED) 회귀 0건
- Watch/Agent/Gateway API의 권한 누락 엔드포인트 0건

## Gate C2: 데이터/이벤트
- Outbox→Redis Streams 전달 멱등성 검증 완료
- DB 스키마 제약/인덱스 검증 완료(무결성 위반 0건)
- Saga 보상 경로 재실행 시 데이터 불일치 0건

## Gate C3: 보안/운영
- 멀티테넌트 격리(RLS+Context) 우회 시나리오 실패(우회 불가)
- Critical/High 취약점 0건
- 배포/롤백/장애복구 리허설 완료(RTO/RPO 목표 충족)
