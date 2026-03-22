# Axiom Multi-tenant Process Graph + Digital Twin Skeleton

이 아카이브는 **Axiom 멀티테넌트 프로세스 그래프 + 디지털 트윈** 설계를 기반으로,
Spring Boot/WebFlux + R2DBC + Neo4j + Flyway 적용을 위한 **구현 골격**입니다.

## 포함 범위

- Flyway SQL 마이그레이션 초안
- PostgreSQL 엔티티 / Enum / Repository 골격
- TenantContext 전파용 WebFilter 예시
- Controller / DTO / Service 인터페이스 골격
- Neo4j Projection용 Cypher 예시
- Outbox 이벤트 모델 골격

## 전제

- Java 21+
- Spring Boot 3.x
- Spring WebFlux
- Spring Data R2DBC
- Spring Data Neo4j 또는 Neo4j Java Driver
- Flyway (JDBC 전용 마이그레이션 용도)
- PostgreSQL 15+
- Neo4j 5+

## 권장 패키지 루트

`com.axiom.platform`

## 주의

이 코드는 **바로 컴파일되는 완성품**이 아니라, 빠르게 구현 착수할 수 있도록 만든
실무용 골격입니다. 프로젝트의 실제 공통 라이브러리/보안 체계/예외 처리 규약에 맞게
다듬어 사용해야 합니다.
