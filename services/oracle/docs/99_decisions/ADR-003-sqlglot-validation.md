# ADR-003: SQLGlot 구조적 SQL 검증

## 상태

Accepted

## 배경

LLM이 생성한 SQL을 실행하기 전에 안전성과 구조적 올바름을 검증해야 한다. 검증 방식을 선택해야 한다:

1. **SQLGlot**: Python 기반 SQL 파서/트랜스파일러, AST 기반 분석
2. **정규표현식 기반**: 문자열 패턴 매칭으로 검증
3. **sqlparse**: Python SQL 파싱 라이브러리
4. **DB EXPLAIN**: 실제 DB에 EXPLAIN 쿼리로 검증

## 고려한 옵션

### 옵션 A: SQLGlot

**장점**:
- **AST 기반 정밀 분석**: SQL을 구문 트리로 파싱하여 정확한 구조 분석
- **다중 SQL 방언 지원**: PostgreSQL, MySQL, BigQuery 등 20+ 방언 파싱/변환
- **구조적 쿼리 가능**: JOIN 수, 서브쿼리 깊이, 테이블 참조 등을 AST에서 추출
- **트랜스파일**: SQL 방언 간 변환 (MySQL -> PostgreSQL)
- **가벼운 의존성**: 순수 Python, 외부 의존 없음
- **K-AIR에서 사용**: `sql_guard.py`에서 SQLGlot 사용 중

**단점**:
- 모든 SQL 방언의 100% 파싱을 보장하지 않음
- 복잡한 프로시저/DDL 파싱이 불완전할 수 있음

### 옵션 B: 정규표현식 기반

**장점**:
- 구현 단순
- 외부 의존 없음
- 빠른 실행 속도

**단점**:
- **오탐/미탐 높음**: 문자열 패턴 매칭은 SQL 문맥을 이해하지 못함
  - 예: `SELECT delete_date FROM ...` → "DELETE" 키워드 오탐
  - 예: `UNION ALL (SELECT ... JOIN ...)` → JOIN 깊이 계산 불가
- 구조적 분석 불가 (서브쿼리 깊이, JOIN 수 등)

### 옵션 C: sqlparse

**장점**:
- Python SQL 파싱 표준 라이브러리
- 토큰화 지원

**단점**:
- AST 수준의 정밀 분석이 SQLGlot보다 약함
- 방언별 차이 처리 미흡
- 구조적 쿼리(JOIN 깊이 등) 직접 구현 필요

### 옵션 D: DB EXPLAIN

**장점**:
- 실제 DB가 검증하므로 100% 정확
- 실행 계획 기반 성능 예측 가능

**단점**:
- **DB 왕복 필요**: 네트워크 지연 추가
- **보안 위험**: 위험한 SQL이 DB에 도달 (EXPLAIN이라도)
- 일부 DDL/DML은 EXPLAIN에서도 부분 실행 가능 (DB에 따라)

## 선택한 결정

**옵션 A: SQLGlot**

## 근거

1. **AST 기반 정밀성**: JOIN 수, 서브쿼리 깊이, 테이블 참조 등을 정확히 측정할 수 있다. 정규표현식으로는 불가능한 "컬럼명에 포함된 키워드(delete_date)"와 "실제 DELETE 문" 구별이 가능하다.

2. **DB 접근 없는 검증**: SQL Guard는 DB에 도달하기 **전에** 위험 SQL을 차단해야 한다. EXPLAIN 방식은 이 원칙에 위배된다.

3. **방언 지원**: Target DB가 PostgreSQL과 MySQL 모두 가능하므로, 방언별 파싱이 필요하다.

4. **K-AIR 검증**: `sql_guard.py`에서 SQLGlot을 사용하여 안정적으로 동작하고 있다.

5. **트랜스파일 잠재력**: 향후 SQL 방언 변환이 필요할 때 활용 가능 (MySQL -> PostgreSQL 이관 등).

## 결과

### 긍정적 영향

- 정밀한 SQL 구조 분석으로 오탐/미탐 최소화
- DB에 위험 SQL이 도달하지 않음
- K-AIR SQL Guard 코드 직접 재사용

### 부정적 영향

- 극히 복잡한 SQL에서 파싱 실패 가능
- SQLGlot 버전 업데이트 시 파싱 동작 변경 가능

### 완화 전략

- SQLGlot 파싱 실패 시 키워드 기반 폴백 검증 (Layer 1)
- SQLGlot 버전 고정 + 업그레이드 시 테스트 수행
- 파싱 실패 로그를 모니터링하여 패턴 분석

## 재평가 조건

- SQLGlot의 파싱 실패율이 5%를 초과할 때
- DB EXPLAIN 기반 검증이 더 효율적임이 증명될 때

---

**근거 문서**: [01_architecture/sql-guard.md](../01_architecture/sql-guard.md)
**영향 문서**: [03_backend/service-structure.md](../03_backend/service-structure.md), [07_security/sql-safety.md](../07_security/sql-safety.md)
