# Axiom Semantic Layer 아키텍처

## 1. 목적
- 레거시 원본 DB를 수정하지 않고, 플랫폼이 AI 친화적 의미 계층을 제공하는 구조를 정의한다.
- Weaver(Data Fabric/Metadata SSOT), Synapse(Ontology), Vision(Data Mart/OLAP)의 책임 경계를 단일 용어로 통합한다.

## 2. 정의
- Semantic Layer는 원본 데이터 저장소 위에 위치한 논리 계층이다.
- 이 계층은 데이터를 "비즈니스 용어/관계/정책"으로 해석 가능하게 만들며, 원본 스키마 변경 권한을 갖지 않는다.

## 3. 구성 요소
1. Weaver Metadata SSOT
- 다중 DB 연결, 메타데이터 추출, 스냅샷, 변경 전파
- Table/Column/FK 및 용어 사전(Planned)의 소유자

2. Synapse Ontology Layer
- 4-Layer Ontology(Resource/Process/Measure/KPI)
- 문서/이벤트 기반 의미 매핑 및 관계 탐색

3. Vision Analytical Mart Layer
- OLTP를 직접 변형하지 않고 Materialized View/ETL로 분석용 모델 제공

## 4. 핵심 원칙
1. Read-only Legacy Access
- 레거시 원본 DB는 조회 중심으로 접근한다.

2. Semantic First
- 질의/분석/AI 추론은 원본 물리 스키마가 아니라 의미 계층(Glossary/Ontology/Metadata)을 우선 참조한다.

3. Controlled Write Path
- 쓰기는 플랫폼 전용 저장소(스냅샷, MV, 온톨로지, 캐시)에서만 수행한다.

## 5. 운영 경계
- Oracle은 Synapse/Weaver를 경유해 컨텍스트를 읽고, 원본 그래프/원본 DB를 임의 수정하지 않는다.
- Canvas는 서비스 API를 통해서만 접근하며, 프론트엔드에서 임의 조합 BFF 로직을 증식하지 않는다.

## 6. 참조 문서
- `docs/legacy-data-isolation-policy.md`
- `services/weaver/docs/01_architecture/data-fabric.md`
- `services/weaver/docs/01_architecture/metadata-service.md`
- `services/synapse/docs/06_data/ontology-model.md`
- `services/vision/docs/03_backend/etl-pipeline.md`
