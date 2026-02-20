# ADR-001: Neo4j 5 선택 근거

## 상태

Accepted

## 배경

Axiom Synapse는 비즈니스 프로세스 데이터를 온톨로지 기반 지식그래프로 구축해야 한다. 이를 위해 그래프 데이터베이스가 필요하다. K-AIR 프로젝트에서 이미 Neo4j를 사용하고 있었으며, text2sql의 벡터 검색과 FK 그래프 탐색 코드를 이식해야 한다.

핵심 요구사항:
- 4계층 온톨로지 (Resource → Process → Measure → KPI) 계층 탐색
- 벡터 유사도 검색 (테이블/컬럼/쿼리 임베딩)
- FK 관계 기반 경로 탐색 (최대 3홉)
- 대규모 가변 경로 쿼리 성능
- K-AIR text2sql 코드 이식 용이성

## 검토한 옵션

### 옵션 1: Neo4j 5 Community

- 네이티브 그래프 DB, Cypher 쿼리 언어
- Neo4j 5부터 벡터 인덱스 내장 지원
- K-AIR에서 이미 사용 중, 코드 이식 용이
- Community 라이선스 (무료)
- 단점: 클러스터링 미지원 (Enterprise만), 온라인 백업 미지원

### 옵션 2: Amazon Neptune

- AWS 관리형 그래프 DB
- Gremlin/SPARQL 쿼리 언어
- 벡터 검색 미지원 (별도 OpenSearch 필요)
- 단점: K-AIR 코드 재작성 필요, 벡터 검색 별도 인프라

### 옵션 3: PostgreSQL + Apache AGE

- PostgreSQL 위에 그래프 확장
- pgvector와 동일 DB에서 운영 가능
- 단점: 경로 탐색 성능 Neo4j 대비 열세, 생태계 미성숙

### 옵션 4: ArangoDB

- 멀티모델 DB (문서 + 그래프 + 키밸류)
- 벡터 인덱스 지원
- 단점: K-AIR 코드 전면 재작성, 한국어 생태계 취약

## 선택한 결정

**Neo4j 5 Community** 를 선택한다.

## 근거

1. **K-AIR 이식 비용 최소화**: text2sql의 `neo4j_bootstrap.py`, `graph_search.py` 코드를 동기→비동기 전환만으로 이식 가능 (3일)

2. **벡터 인덱스 내장**: Neo4j 5부터 벡터 인덱스를 네이티브로 지원하여, 별도 벡터 DB 없이 그래프 + 벡터 통합 검색 가능

3. **경로 탐색 성능**: 가변 길이 경로 탐색 (`*1..4`)에서 Neo4j는 네이티브 그래프 저장소의 인접 리스트 탐색으로 O(k^d) 성능 보장 (k=평균 이웃 수, d=깊이). RDBMS의 재귀 JOIN 대비 10-100배 빠름

4. **Cypher 가독성**: 4계층 온톨로지 경로 탐색 쿼리가 직관적
   ```cypher
   MATCH path = (r:Resource)-[:PARTICIPATES_IN]->(p:Process)
                 -[:PRODUCES]->(m:Measure)-[:CONTRIBUTES_TO]->(k:KPI)
   RETURN path
   ```

5. **Oracle 모듈 호환**: Oracle Text2SQL이 이미 Neo4j 벡터 검색에 의존하므로 DB 전환 시 Oracle도 함께 변경 필요

## 결과

### 긍정적 영향

- K-AIR 코드 이식 비용 3일 (다른 옵션은 2-4주)
- 벡터 + 그래프 통합 검색으로 인프라 단순화
- Cypher 쿼리 언어로 온톨로지 탐색 코드 가독성 향상

### 부정적 영향

- Community 버전은 클러스터링 미지원 (단일 노드 한계)
- Community 버전은 온라인 백업 미지원 (다운타임 백업 필요)
- Neo4j 전문 인력 필요

### 완화 방안

- 단일 노드 한계: 현재 예상 데이터 규모 (케이스당 수백 노드)에서는 충분. 향후 규모 증가 시 Enterprise 전환 검토
- 백업: 야간 유지보수 시간에 dump 백업 수행
- 인력: Cypher 학습 비용은 SQL 대비 낮음

## 재검토 조건

- Neo4j 단일 노드 성능이 동시 사용자 100명 이상에서 한계를 보일 때
- 벡터 검색 성능이 pgvector 대비 현저히 저하될 때
- Neo4j 라이선스 정책이 변경될 때
- AWS Neptune이 벡터 인덱스를 네이티브로 지원할 때
