# ADR-001: MindsDB 데이터 패브릭 게이트웨이 선택

## 상태

Accepted

## 배경

Axiom 플랫폼은 비즈니스 프로세스 인텔리전스를 위해 **다수의 이종 데이터베이스**에 분산된 데이터를 통합 조회해야 한다. ERP DB(PostgreSQL), 재무 시스템 DB(MySQL/Oracle), 문서 저장소(MongoDB) 등이 물리적으로 분리되어 있으며, 사용자와 AI 에이전트는 이들을 **단일 인터페이스**로 접근해야 한다.

데이터 패브릭 게이트웨이는 이 다중 DB를 추상화하는 핵심 컴포넌트이다. K-AIR 프로젝트에서 이미 MindsDB를 데이터 패브릭으로 사용한 경험(robo-data-fabric-main, 85% 구현)이 있다.

## 고려한 옵션

### 옵션 1: MindsDB

- 오픈소스 AI-DB 플랫폼
- MySQL/PostgreSQL 프로토콜 호환
- 다중 DB 핸들러 내장 (PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch 등)
- ML 모델 통합 (CREATE PREDICTOR)
- HTTP API + SQL 인터페이스
- K-AIR에서 이미 검증됨

### 옵션 2: Apache Trino (구 PrestoSQL)

- 분산 SQL 쿼리 엔진
- 커넥터 기반 다중 DB 접근
- 대규모 분석 쿼리에 강점
- Java 기반, 운영 복잡도 높음
- ML 통합 없음

### 옵션 3: 직접 구현 (SQLAlchemy + 라우터)

- SQLAlchemy로 각 DB 세션 관리
- 자체 SQL 파서로 DB 라우팅
- 크로스 DB 조인은 메모리 내 처리
- 완전한 제어 가능
- 개발 비용 매우 높음

### 옵션 4: Denodo / Dremio (상용)

- 엔터프라이즈 데이터 가상화
- 강력한 성능 최적화
- 높은 라이선스 비용
- 벤더 종속

## 선택한 결정

**옵션 1: MindsDB**를 Weaver의 데이터 패브릭 게이트웨이로 선택한다.

## 근거

1. **K-AIR 검증 경험**: robo-data-fabric-main에서 85% 구현 상태로, PostgreSQL/MySQL 연동이 안정적으로 동작함을 확인
2. **ML 통합**: MindsDB의 CREATE PREDICTOR를 통해 ML 예측 모델을 SQL로 호출 가능 → AI 데이터 플랫폼 비전에 부합
3. **운영 단순성**: Docker 단일 컨테이너 배포, 별도 클러스터 불필요
4. **HTTP API**: REST API를 통한 SQL 실행 → FastAPI와 자연스러운 통합
5. **SQL 표준 인터페이스**: 사용자와 AI 에이전트 모두 SQL로 통일된 접근 → NL2SQL(Oracle 모듈)과 직접 연동
6. **비용**: 오픈소스, 라이선스 비용 없음

### MindsDB의 한계 (인정)

- **스키마 인트로스펙션 부족**: MindsDB는 대상 DB의 스키마를 자세히 추출하지 못함 → 어댑터 패턴으로 직접 구현 (ADR-002)
- **크로스 DB 조인 성능**: 대규모 테이블 조인 시 메모리 내 처리로 성능 저하 → 물리화 테이블(Materialized Table)로 완화
- **HA 구성 제한**: 단일 인스턴스 → 스케일 아웃 시 별도 아키텍처 필요 (Phase 4+)

## 결과

### 긍정적 영향

- K-AIR 코드 직접 이식으로 개발 기간 단축 (3일)
- 단일 SQL 인터페이스로 Oracle(NL2SQL), Vision(분석) 모듈 통합 용이
- ML 예측 모델을 데이터 접근 계층에서 바로 사용 가능

### 부정적 영향

- MindsDB 서버 장애 시 모든 쿼리 실행 불가 (단일 장애점)
- MindsDB 버전 업그레이드에 Weaver가 영향 받음
- 대규모 크로스 DB 조인 시 성능 병목

## 재평가 조건

- MindsDB의 성능이 동시 사용자 50명 이상에서 병목이 되는 경우
- MindsDB 프로젝트의 라이선스 변경 또는 개발 중단
- Axiom 사용자 수가 1000명을 초과하여 HA 구성이 필수가 되는 경우
- 크로스 DB 조인 쿼리 응답 시간이 10초를 초과하는 경우가 빈번한 경우

## 근거 자료

- K-AIR 역설계 분석 보고서: `research/k-air-reverse-engineering-analysis.md`
- K-AIR 아키텍처 결정 #3: "MindsDB로 데이터 패브릭 구현"
- K-AIR 구현 현황: robo-data-fabric-main (85% 구현)
