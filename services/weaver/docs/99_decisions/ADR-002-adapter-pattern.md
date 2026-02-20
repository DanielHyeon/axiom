# ADR-002: 어댑터 패턴 기반 스키마 인트로스펙션

## 상태

Accepted

## 배경

Weaver는 연결된 데이터베이스의 스키마(테이블, 컬럼, FK 관계)를 자동으로 추출해야 한다. 이 메타데이터는 Neo4j 그래프에 저장되어 Oracle(NL2SQL) 모듈이 자연어 질의를 SQL로 변환할 때 핵심 컨텍스트로 사용된다.

**문제**: MindsDB는 쿼리 실행(SELECT, INSERT 등)은 지원하지만, **대상 DB의 상세 스키마 정보(컬럼 타입, nullable, FK 관계, 코멘트)**를 추출하는 기능이 제한적이다. `DESCRIBE` 명령으로 기본 정보만 얻을 수 있으며, FK 관계는 얻을 수 없다.

K-AIR에서는 이 문제를 `schema_introspection.py` (880줄) 단일 파일에 PostgreSQL/MySQL 어댑터를 구현하여 해결했다.

## 고려한 옵션

### 옵션 1: 어댑터 패턴 (Strategy Pattern)

- 각 DB 엔진별 독립적인 어댑터 클래스
- 공통 인터페이스(BaseAdapter) 정의
- 팩토리 패턴으로 엔진별 어댑터 생성
- 새 DB 추가 시 어댑터만 구현

### 옵션 2: MindsDB DESCRIBE 활용

- MindsDB의 기본 DESCRIBE 명령만 사용
- FK 관계, 코멘트 등은 포기
- 구현 단순
- 메타데이터 품질 저하

### 옵션 3: 단일 서비스에 if-else 분기

- K-AIR처럼 단일 파일에 모든 엔진 로직 포함
- if engine == "postgresql" / elif engine == "mysql" 분기
- 파일 크기 증가 (K-AIR: 880줄, Oracle 추가 시 1200줄+)

### 옵션 4: SQLAlchemy Inspector 활용

- SQLAlchemy의 `inspect()` 메서드로 스키마 추출
- 다중 DB 지원이 SQLAlchemy에 위임
- FK, PK 정보 기본 제공
- 비동기 지원 제한, 코멘트 추출 어려움

## 선택한 결정

**옵션 1: 어댑터 패턴**을 선택한다.

## 근거

1. **확장성**: Oracle 어댑터를 신규 추가해야 하며, 향후 SQL Server, Snowflake 등도 추가될 수 있음. 어댑터 패턴은 기존 코드 변경 없이 확장 가능 (Open/Closed Principle)

2. **DB별 최적화**: 각 DB는 스키마 조회 SQL이 근본적으로 다름
   - PostgreSQL: `information_schema` + `pg_catalog`
   - MySQL: `information_schema.COLUMNS/TABLES`
   - Oracle: `ALL_TAB_COLUMNS`, `ALL_CONSTRAINTS`
   - 각 DB의 고유 기능(PG의 `col_description`, Oracle의 `ALL_COL_COMMENTS`)을 최대한 활용해야 정확한 메타데이터를 얻을 수 있음

3. **비동기 지원**: PostgreSQL(asyncpg), MySQL(aiomysql)은 각각 고유한 비동기 드라이버를 사용. 어댑터별 독립적인 비동기 구현이 가능

4. **테스트 용이성**: 어댑터별 독립 단위 테스트 가능. Mock 어댑터로 통합 테스트도 용이

5. **K-AIR 코드 재사용**: K-AIR의 PostgreSQL/MySQL 로직을 그대로 이식하되, 파일만 분리

### 왜 SQLAlchemy Inspector가 아닌가

- SQLAlchemy Inspector는 동기 전용 (`async_sessionmaker`로도 inspect는 동기)
- 코멘트(COMMENT ON) 추출이 DB별로 불완전
- FK 정보는 제공하나, 커스텀 메타데이터(Oracle의 ALL_TAB_COMMENTS 등)에 접근 제한
- Weaver는 DB별 카탈로그 뷰에 직접 접근하여 최대한 풍부한 메타데이터를 추출해야 함

## 결과

### 긍정적 영향

- K-AIR의 880줄 단일 파일 → 어댑터별 200-300줄 파일로 분리 (유지보수성 향상)
- Oracle 어댑터 신규 추가 (대형 엔터프라이즈 DB 지원)
- 향후 SQL Server, Snowflake 등 추가 시 기존 코드 무변경
- 어댑터별 독립 테스트 가능

### 부정적 영향

- 파일 수 증가 (1개 → 5개)
- 새 어댑터 추가 시 BaseAdapter의 모든 추상 메서드 구현 필요
- 공통 로직 변경 시 모든 어댑터 영향 검토 필요

## 재평가 조건

- 지원 DB 엔진이 10개를 초과하여 공통 로직 추출이 필요한 경우
- SQLAlchemy가 완전한 비동기 Inspector를 지원하게 되는 경우
- MindsDB가 상세 스키마 인트로스펙션 기능을 추가하는 경우

## 근거 자료

- K-AIR `schema_introspection.py` (880줄): PostgreSQL/MySQL 구현 참조
- 설계 문서: `01_architecture/adapter-pattern.md`
