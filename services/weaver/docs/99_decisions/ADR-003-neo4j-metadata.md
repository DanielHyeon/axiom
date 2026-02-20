# ADR-003: Neo4j 메타데이터 그래프 저장소 선택

## 상태

Accepted

## 배경

Weaver가 추출한 메타데이터(DataSource, Schema, Table, Column, FK 관계)를 저장하고 탐색할 저장소가 필요하다. 이 메타데이터는 다음 목적으로 사용된다:

1. **Oracle(NL2SQL)**: 자연어 질의를 SQL로 변환할 때 테이블/컬럼/FK 컨텍스트 제공
2. **Canvas(UI)**: 사용자에게 스키마 브라우저 제공
3. **LLM 보강**: 테이블/컬럼 설명 자동 생성 후 저장
4. **조인 경로 탐색**: FK 기반으로 테이블 간 조인 경로를 자동 발견

특히 **FK 경로 탐색**은 핵심 요구사항이다. "조직(organization) 테이블에서 거래(transaction) 테이블까지 어떤 조인 경로가 있는가?"라는 질문에 답해야 한다.

K-AIR에서는 robo-data-fabric과 robo-data-text2sql 모두 Neo4j를 메타데이터 저장소로 사용했다.

## 고려한 옵션

### 옵션 1: Neo4j (그래프 DB)

- 네이티브 그래프 데이터베이스
- Cypher 쿼리 언어
- FK 경로 탐색이 자연스러움 (shortestPath)
- 벡터 인덱스 지원 (5.x+)
- K-AIR에서 이미 사용 중

### 옵션 2: PostgreSQL JSONB

- 이미 Axiom Core에서 사용 중인 PostgreSQL에 저장
- JSONB 타입으로 계층 구조 저장
- 별도 DB 운영 불필요
- 그래프 탐색은 재귀 CTE로 구현 (복잡)

### 옵션 3: PostgreSQL + pg_graph 확장

- PostgreSQL 위에 그래프 기능 추가
- openCypher 쿼리 일부 지원
- 에코시스템 미성숙

### 옵션 4: ArangoDB (멀티모델)

- 그래프 + 문서 + KV 통합
- AQL 쿼리 언어
- K-AIR 경험 없음
- 운영 경험 부재

## 선택한 결정

**옵션 1: Neo4j**를 메타데이터 그래프 저장소로 선택한다.

## 근거

1. **FK 경로 탐색 성능**: `shortestPath` 알고리즘으로 N홉 FK 경로를 밀리초 내에 탐색. PostgreSQL 재귀 CTE로 동일 기능 구현 시 복잡도와 성능 모두 열위

   ```cypher
   -- Neo4j: 직관적이고 빠름
   MATCH path = shortestPath(
     (t1:Table {name: 'organizations'})-[:FK_TO_TABLE*1..3]-(t2:Table {name: 'transactions'})
   )
   RETURN path
   ```

   ```sql
   -- PostgreSQL: 복잡하고 느림
   WITH RECURSIVE fk_path AS (
     SELECT source_table, target_table, 1 as depth, ARRAY[source_table] as path
     FROM foreign_keys WHERE source_table = 'organizations'
     UNION ALL
     SELECT fk.source_table, fk.target_table, fp.depth + 1, fp.path || fk.source_table
     FROM foreign_keys fk JOIN fk_path fp ON fk.source_table = fp.target_table
     WHERE fp.depth < 3 AND NOT fk.source_table = ANY(fp.path)
   )
   SELECT path FROM fk_path WHERE target_table = 'transactions';
   ```

2. **K-AIR 검증 경험**: robo-data-fabric과 robo-data-text2sql 모두 Neo4j를 사용하여 메타데이터 + 벡터 검색을 수행. 안정적으로 동작함을 확인

3. **Oracle(NL2SQL) 연동**: Oracle 모듈의 text2sql도 Neo4j에서 스키마 컨텍스트를 조회. 메타데이터가 Neo4j에 있으면 Oracle이 직접 접근 가능 (Weaver API 경유 불필요)

4. **벡터 인덱스**: Neo4j 5.x의 벡터 인덱스를 활용하면, 향후 메타데이터 벡터 검색("매출 관련 테이블 찾기")도 같은 저장소에서 가능

5. **자연스러운 데이터 모델**: DataSource→Schema→Table→Column 계층 구조가 그래프로 자연스럽게 표현됨

### 왜 PostgreSQL JSONB가 아닌가

- FK 경로 탐색에 재귀 CTE 필요 → 코드 복잡도 증가
- 3홉 이상 탐색 시 성능 급감
- JSONB 안에 중첩된 구조 업데이트가 불편 (LLM 보강 시 개별 컬럼 description 업데이트)
- Oracle 모듈이 이미 Neo4j를 사용하므로, 별도 저장소를 추가하면 인프라 복잡도만 증가

## 결과

### 긍정적 영향

- FK 경로 탐색이 자연스럽고 성능 우수
- K-AIR 코드 직접 이식 가능 (Cypher 쿼리 재사용)
- Oracle 모듈과 메타데이터 저장소 공유 가능
- 향후 벡터 인덱스 활용 가능

### 부정적 영향

- Neo4j 서버 별도 운영 필요 (인프라 추가)
- Neo4j 라이선스 확인 필요 (Community Edition은 일부 기능 제한)
- Neo4j 장애 시 메타데이터 조회 불가 (쿼리 실행은 MindsDB로 독립 동작)
- 학습 곡선: Cypher 쿼리 언어

## 재평가 조건

- Neo4j Community Edition의 기능 제한이 Axiom 운영에 장애가 되는 경우
- 메타데이터 규모가 Neo4j 단일 서버 한계(수억 노드)에 근접하는 경우
- PostgreSQL에 Apache AGE 등 성숙한 그래프 확장이 등장하는 경우
- Oracle 모듈이 Neo4j를 사용하지 않기로 결정하는 경우

## 근거 자료

- K-AIR 역설계 분석 보고서: "Neo4j를 메타데이터 + 벡터 저장소로" (결정 #2)
- K-AIR Neo4j 스키마: robo-data-fabric + robo-data-text2sql
- 설계 문서: `06_data/neo4j-schema.md`
