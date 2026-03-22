# 구현 메모

## 1. 멀티테넌트 강제 방식
- 인증 토큰에서 tenant membership 검증
- Gateway 또는 BFF 레벨에서 X-Tenant-Id 주입
- WebFlux 필터에서 TenantContext 생성
- Repository 직접 호출보다 Service 계층에서 tenant 검증 강제

## 2. PostgreSQL ↔ Neo4j 동기화
권장 흐름:
1. R2DBC 트랜잭션 내 도메인 엔티티 저장
2. OutboxEvents에 projection 이벤트 적재
3. 별도 Publisher/Projector가 Neo4j MERGE 실행
4. 실패 시 dead-letter 또는 retry queue 사용

즉시 동기 호출도 가능하지만, 운영 안정성을 위해 최종적으로는 비동기 projection을 권장

## 3. 시나리오 엔진 최소 버전
초기에는 정교한 DES(Discrete Event Simulation)보다 rule-based delta simulation 으로 시작:
- 자동화율 증가 → 평균 처리시간 감소율 적용
- 병렬 인력 증가 → queue length 감소율 적용
- 승인 기준 강화 → 재검토율/민원율 변화 적용
- KPI 결과를 before/after 형태로 비교

## 4. 다음 단계 추천
- Flyway SQL을 실제 naming rule에 맞게 분할
- repository custom query 추가
- @ReadingConverter/@WritingConverter 로 JSONB 처리
- Neo4j projection worker / scheduler 추가
- integration testcontainer 세팅
