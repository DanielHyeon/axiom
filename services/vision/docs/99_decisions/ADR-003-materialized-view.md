# ADR-003: Materialized View vs 별도 DW 인스턴스

## 상태

Accepted

## 배경

OLAP 분석을 위해 Star Schema(팩트/디멘전 테이블)를 구성해야 한다. 이 데이터를 어디에, 어떤 형태로 저장할지 결정해야 한다.

### 요구사항

- OLTP 트랜잭션에 영향 없이 분석 쿼리 실행
- 수천 ~ 수만 건 규모의 데이터 (초대규모 아님)
- 일 1회 + 이벤트 기반 동기화
- 인프라 비용 및 운영 복잡도 최소화 (MVP 단계)
- 무중단 데이터 갱신 (쿼리 차단 없이)

## 고려한 옵션

### 1. PostgreSQL Materialized View (동일 인스턴스)

- **장점**: 추가 인프라 불필요, PostgreSQL 네이티브 기능, CONCURRENTLY REFRESH로 무중단 갱신, 운영 복잡도 최소
- **단점**: OLTP 인스턴스에 분석 부하 추가, REFRESH 시 CPU/IO 사용, 대규모 데이터(수천만 건+) 시 성능 한계

### 2. 별도 PostgreSQL Read Replica + Materialized View

- **장점**: OLTP 인스턴스 부하 분리, 동일 기술 스택
- **단점**: 추가 인프라 비용, 복제 지연(lag), 운영 복잡도 증가

### 3. 별도 DW (Amazon Redshift / ClickHouse)

- **장점**: 대규모 분석에 최적화, 열 저장(columnar) 방식으로 빠른 집계
- **단점**: 추가 인프라 비용 높음, 기술 스택 추가, ETL 파이프라인 복잡도 증가, MVP에 과도한 투자

### 4. Apache Kylin + HBase

- **장점**: 사전 집계(pre-aggregation)로 매우 빠른 쿼리
- **단점**: HBase 인프라 필요, 운영 복잡도 매우 높음, 데이터 규모 대비 과도한 솔루션

### 5. dbt + PostgreSQL

- **장점**: 데이터 변환 파이프라인 표준화, 테스트/문서화 내장
- **단점**: dbt 학습 곡선, MVP 단계에서 추가 도구 도입 부담, MV만으로 충분한 상황

## 선택한 결정

**PostgreSQL Materialized View (동일 인스턴스)**

## 근거

1. **데이터 규모 적합성**: 현재 예상 데이터는 사건 수천 건, 이해관계자 수만 건 수준. 이 규모에서 MV REFRESH는 수십 초면 충분하며, 별도 DW는 과잉 투자.

2. **인프라 최소화**: MVP 단계에서 추가 인프라(Redshift, ClickHouse) 도입은 비용과 운영 부담을 증가시킴. 동일 PostgreSQL 인스턴스의 MV로 충분한 성능 달성 가능.

3. **CONCURRENTLY REFRESH**: PostgreSQL의 CONCURRENTLY 옵션으로 읽기 차단 없이 MV 갱신 가능. 서비스 가용성 보장.

4. **점진적 확장 가능**: 데이터 규모 증가 시 Read Replica 추가 또는 별도 DW 전환이 가능. MV 기반 Star Schema는 그대로 유지하고 저장소만 교체하면 됨.

5. **단일 기술 스택**: PostgreSQL만 알면 OLTP + OLAP 모두 운영 가능. 팀 학습 비용 없음.

## 결과

### 긍정적 영향

- MVP 단계에서 인프라 비용 0원 추가
- 운영 복잡도 최소 (PostgreSQL 하나만 관리)
- 개발 속도 빠름 (CREATE MATERIALIZED VIEW 한 줄)
- OLTP 스키마 변경 시 MV 정의만 수정하면 자동 반영

### 부정적 영향

- OLTP 인스턴스에 REFRESH 부하 추가 (새벽 3시 스케줄링으로 완화)
- 데이터 규모 수십만 건 이상 시 REFRESH 시간 증가 가능
- 실시간에 가까운 분석 불가 (최소 갱신 주기 5분)

## 재평가 조건

- OLAP 쿼리 응답 시간이 일관되게 5초 이상일 때
- MV REFRESH가 일관되게 5분 이상 소요될 때
- OLTP 인스턴스 CPU 사용률이 REFRESH로 인해 70% 이상일 때
- 데이터 규모가 10만 건 이상으로 성장할 때
- 실시간 분석(지연 < 1분)이 비즈니스 요구사항이 될 때

### 확장 경로

```
현재: PostgreSQL MV (동일 인스턴스)
  ↓ 데이터 증가 시
Stage 1: PostgreSQL Read Replica + MV
  ↓ 더 큰 규모 시
Stage 2: ClickHouse 또는 Redshift (컬럼나 DW)
  ↓ 실시간 필요 시
Stage 3: Materialized View + CDC (Debezium)
```

---

## 증거

- 06_data/data-warehouse.md (MV DDL 상세)
- 03_backend/etl-pipeline.md (REFRESH 전략)
- 01_architecture/olap-engine.md Section 4
