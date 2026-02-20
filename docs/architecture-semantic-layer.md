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

## 3.1 4-Source Ingestion 표준
- Semantic Layer 입력은 아래 4개 소스를 표준 소스군으로 관리한다.
1. 운영 DB/데이터웨어하우스
- 구조화 데이터, 스키마/제약조건/FK를 제공한다.
2. 레거시 코드
- 도메인 규칙(aggregate/invariant/policy) 발굴 근거를 제공한다.
3. 공식 문서/SOP/규정
- 컴플라이언스 제약과 표준 운영 절차를 제공한다.
4. 산업 표준 온톨로지/외부 레퍼런스
- 내부 데이터가 비어 있는 영역의 의미 모델을 보강한다.

## 3.2 Golden Question 공식 방법론 및 필터
- 대량 원천 데이터는 전량 모델링하지 않고, 비즈니스 목적의 "질문(Golden Question)" 기반 필터링을 최우선으로 선행한다.

### 3.2.1 표준 입력 템플릿
모든 신규 온톨로지/분석 모델은 다음 양식을 통해 도출 목적을 명시해야 한다.
1. **Golden Question**: 해결하고자 하는 비즈니스 질문 (예: "지난 달 북미 리테일 고객 이탈의 주된 요인은?")
2. **비즈니스 액션 (Action)**: 이 질문의 답변을 통해 실행할 조치
3. **핵심 분석 지표 (Metrics)**: 질문에 답하기 위해 필요한 정량적 측정 항목
4. **필요 데이터 소스 (Sources)**: 추적 대상 레거시 스키마 또는 문서

### 3.2.2 품질 게이트 (Quality Gate)
- 데이터 모델/온톨로지 추가 PR은 반드시 최소 1개 이상의 Golden Question Triage 템플릿이 첨부되어야 한다.
- 목적(Golden Question)이 모호하거나 연결되지 않은 "단순 데이터 적재/매핑용" 스키마 변경은 구조 리뷰어(Code Reviewer)에 의해 반려(Reject)된다.

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

## 5.1 DB 계층 운영 원칙
- DB별 물리 위치/종류(SQL, NoSQL, Legacy)는 Semantic Layer 하위 구현 세부사항으로 취급한다.
- 상위 서비스(Core/Oracle/Vision/Synapse)는 공통 의미 계약(Glossary/Ontology/Metadata/Event Contract)으로만 접근한다.
- DB 쓰기 경로는 감사 가능해야 하며, 원본 불변 정책 위반 경로를 금지한다.

## 6. 참조 문서
- `docs/legacy-data-isolation-policy.md`
- `docs/domain-contract-registry.md`
- `services/weaver/docs/01_architecture/data-fabric.md`
- `services/weaver/docs/01_architecture/metadata-service.md`
- `services/synapse/docs/06_data/ontology-model.md`
- `services/vision/docs/03_backend/etl-pipeline.md`
