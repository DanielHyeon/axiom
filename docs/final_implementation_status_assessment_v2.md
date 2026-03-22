# 최종 구현 상태 평가서 v2

작성일: 2026-03-23  
대상: Ontology-driven Semantic Layer 구현 상태 종합 평가

---

## 1. 최종 판정

현재 시스템은 **Ontology-driven Semantic Layer의 핵심 메타모델, 관리 API, 컴파일러, 카탈로그 UI, AI Context 주입 기반**을 상당 부분 구현했다.  
다만 **Oracle 소비단에서의 계약 준수 강제, 품질 점수의 행동 연계, 계약 변경의 일관성 보장, 도메인 연합 확장**이 아직 미완성이다.

따라서 현재 상태는 다음과 같이 평가한다.

> **Semantic Control Plane은 강하게 구현되었으나, Semantic Enforcement Runtime은 아직 미완성이다.**

즉, “정의·관리 중심의 시맨틱 플랫폼” 단계에는 도달했지만, “실행 강제형 Ontology-driven Semantic Runtime” 단계에는 아직 도달하지 않았다.

---

## 2. 평가 요약

### 2.1 구현률 해석

단순 구현률 수치만으로 보면 약 **65~70% 수준**으로 보인다.  
그러나 이 수치는 전체 비전 대비 구조 구현률에 가깝고, 운영 완성도를 그대로 뜻하지는 않는다.

보다 정확하게는 다음과 같이 구분하는 것이 맞다.

- **비전 대비 구조 구현률**: 65~70%
- **Control Plane 완성도**: 75~85%
- **Enforcement Runtime 완성도**: 45~60%
- **Federation / ML 확장 완성도**: 20~35%

즉, 현재는 “보여주고 관리하고 배포하는 능력”은 강하지만, “실제로 강제하고 신뢰도를 자동 제어하는 능력”은 아직 부족하다.

---

## 3. 영역별 판정

### 3.1 강하게 구현된 영역

#### A. Semantic Contract Core
다음 핵심 구조는 구현 완료로 본다.

- semantic entity
- semantic measure
- semantic dimension
- join contract
- grain contract
- quality contract
- semantic release

이는 L2 시맨틱 계약 계층의 뼈대를 형성하며, 실제 메타모델의 중심 축 역할을 수행한다.

#### B. Ontology Governance Core
다음은 구현 기반이 잘 잡힌 상태다.

- ontology_concepts
- ontology_terms
- 상태 전이 기반 관리
- 바인딩 검증을 위한 개념 참조 구조

이로 인해 “용어 사전” 수준이 아니라 “운영되는 온톨로지”로 가기 위한 최소 조건은 충족했다.

#### C. Semantic Compiler
다음 기능은 매우 중요한 기반으로 평가한다.

- binding 검증
- fanout 위험 감지
- SQL 템플릿 생성
- SQL injection 차단

이는 계약을 단순 저장이 아니라 실행 가능한 형태로 변환하는 핵심 엔진이다.

#### D. Control Surface / Catalog UI
다음 UI 계층은 상당히 잘 구현된 편이다.

- Canvas 시맨틱 카탈로그
- 상태 전이 UI
- 컴파일/배포 UI
- 온톨로지 탐색기
- Cytoscape 기반 의미 그래프
- 임팩트 분석 시각화

즉, 운영자가 구조를 탐색하고 승인하고 배포하는 통제면은 강하다.

#### E. AI Context 기반 주입
다음은 “AI 친화적 소비 계층의 구조물”로서 의미가 있다.

- ContextPack
- PromptPolicy
- Oracle 프롬프트 포맷팅 주입
- graceful fallback
- 의도 기반 컨텍스트 매칭

다만 이는 “기반 구축 완료”이지 “폐루프 완성”으로 보기는 어렵다. 이 부분은 아래에서 다시 다룬다.

---

## 4. 부분 완료로 봐야 하는 영역

### 4.1 AI Context는 완료가 아니라 ‘구조 구축 완료 + 집행 미완성’

다음이 아직 빠져 있다.

- post-generation 계약 준수 검증
- banned join AST 검증
- synonym 확장 적용
- 품질 점수 임계치 연동
- 계약 변경 이벤트 기반 반영
- 캐시 무효화
- 의도 분류 신뢰도 보강

따라서 L5 AI Context는 다음처럼 표현해야 정확하다.

> **AI Context의 정의/주입 구조는 구현되었으나, 소비 후 검증과 동적 반영은 미완성이다.**

### 4.2 품질 엔진은 ‘동작 중’이 아니라 ‘프레임워크 가동 중’

현재 완료된 차원:

- freshness
- completeness
- uniqueness

미완료 또는 사실상 미완료:

- validity
- referential integrity
- test coverage
- incident health
- lineage completeness(하드코딩 0)

즉 품질 엔진은 존재하지만, semantic runtime의 신뢰를 완전히 뒷받침하는 수준은 아니다.

### 4.3 Transactional Outbox는 기반 구현, 의미 폐루프는 미완성

이벤트 발행 구조는 중요한 진전이지만, 다음이 닫히지 않았다.

- 계약 변경 이벤트 소비자 반영
- Oracle 측 캐시 무효화
- semantic snapshot 재고정

즉 “이벤트를 낸다”와 “시스템 전체 의미 상태가 일관되게 갱신된다”는 다르다.

---

## 5. 미구현 또는 실질 미완성 영역

### 5.1 계획서의 추가 테이블 중 미구현

다음은 아직 직접 구현되지 않았거나 우회 대체 상태다.

- semantic_segments
- time_contracts
- access_policies
- ontology_relations (Neo4j 대체)
- ontology_rules (DMN 대체)
- ontology_policies

이 중 일부는 설계상 반드시 RDB 테이블로 있어야 하는 것은 아니지만, “계획서 원안 대비 완전 구현”이라고 말하기는 어렵다.

### 5.2 Semantic Query Runtime 부재

다음 항목은 매우 중요하다.

- `POST /query/metrics` 전용 시맨틱 쿼리 API 부재

현재는 정의/관리/배포 구조는 있으나, 시맨틱 계약을 기준으로 질의를 강제 실행하는 표준 런타임 API가 부족하다.

### 5.3 Federation / Domain Namespace 미구현

Phase 5에서 목표한 다음 항목은 아직 미착수 수준이다.

- namespace 정책
- 도메인별 승인 워크플로
- domain steward 운영 모델
- cross-domain publication rule

즉 중앙 표준은 생겼지만, 도메인 연합 운영 모델은 아직 형성되지 않았다.

### 5.4 ML / Feature 통합 미구현

Phase 6 관련 항목은 사실상 아직 시작 전이다.

- feature source binding
- semantic-to-feature lineage
- training API
- offline/online feature serving 연계

이 때문에 현재 플랫폼은 BI/NL2SQL 중심이며, ML feature semantic plane까지 확장되지는 않았다.

---

## 6. 가장 시급한 갭

### 6.1 1순위 — Oracle 생성 SQL의 계약 준수 사후 검증

현재 가장 위험한 지점이다.

문제:
- LLM이 금지된 조인을 사용해도 차단되지 않음
- 승인되지 않은 테이블을 참조해도 실행 경로로 갈 수 있음
- grain 위반 여부를 사후 강제하지 못함

영향:
- semantic layer가 “권고 시스템”으로 전락할 수 있음
- 운영자가 승인한 계약과 실제 실행 SQL이 어긋날 수 있음
- 신뢰 붕괴 위험이 큼

필수 조치:
- SQL AST 파서 도입
- banned join 검증기
- approved table whitelist 검증기
- grain compatibility 검증기
- violation explanation formatter

### 6.2 2순위 — 품질 점수의 행동 연계

현재는 측정은 일부 되지만, 응답 정책이 거의 바뀌지 않는다.

필수 조치:
- score 기반 응답 등급 정책
- 예시
  - 80 이상: 신뢰 가능
  - 60~79: 주의 필요
  - 40~59: 참고용
  - 39 이하: 자동 차단 또는 재확인 유도
- Oracle 응답 뱃지/문구/근거 노출
- 저품질 지표에 대한 정책형 강등 적용

### 6.3 3순위 — 계약 변경 일관성 보장

현재는 매 요청 동기 조회 또는 stale state 위험 중 하나를 선택해야 하는 구조에 가깝다.

필수 조치:
- semantic snapshot Redis 캐시
- release version pinning
- 계약 변경 이벤트 수신기
- cache invalidation worker
- Oracle 요청별 snapshot reference 고정

이 항목은 단순 성능이 아니라 “같은 질문에 같은 계약이 적용되는가”라는 일관성 문제다.

---

## 7. 위험도 평가

### Critical
- Oracle post-generation 계약 준수 검증 부재
- banned join / forbidden table 차단 부재

### Major
- 품질 점수 임계치 미적용
- ontology synonym 확장 미활용
- semantic snapshot/version consistency 부재
- lineage completeness 미구현

### Medium
- Redis 캐시 부재
- 계약 변경 이벤트 수신 미구현
- semantic query runtime API 부재
- role model 세분화 부족

### Low / Later
- LLM 기반 의도 분류 고도화
- ML/Feature 통합
- domain federation 고도화

---

## 8. 권장 상태 정의

현재 상태를 가장 정확하게 표현하는 공식 문구는 아래와 같다.

> **Axiom은 온톨로지-시멘틱 레이어의 핵심 메타모델, 관리 API, 컴파일러, 카탈로그 UI, AI Context 주입 기반을 상당 부분 구현했다. 그러나 Oracle 소비단에서의 계약 준수 강제, 품질 점수의 행동 연계, 계약 변경의 일관성 보장, 연합 거버넌스 확장이 아직 미완성이다. 따라서 본 시스템은 ‘Semantic Control Plane’ 단계에는 도달했으나, ‘Semantic Enforcement Runtime’ 단계에는 아직 도달하지 않았다.**

---

## 9. 다음 4개 스프린트 권장안

### Sprint 1 — SQL Enforcement Guard
목표: 생성 SQL을 계약 기준으로 차단 가능하게 만들기

구현 항목:
- SQL AST parser
- banned join validator
- allowed relation validator
- approved table validator
- grain mismatch validator
- semantic violation response formatter

완료 기준:
- 금지 조인 생성 시 실행 차단
- 미승인 테이블 참조 시 실행 차단
- 위반 사유가 사용자/운영자에게 설명 가능해야 함

### Sprint 2 — Quality-aware Answer Policy
목표: 품질 점수가 실제 응답 태도와 결과 표시를 바꾸게 만들기

구현 항목:
- quality threshold policy engine
- score band rule
- Oracle response badge integration
- 참고용/주의필요/차단 분기
- lineage completeness 최소 계산 도입

완료 기준:
- score에 따라 응답 등급이 달라짐
- 저품질 데이터는 답변에서 명시적으로 강등됨

### Sprint 3 — Semantic Snapshot Consistency
목표: 계약 변경과 소비자 상태를 일관되게 맞추기

구현 항목:
- Redis semantic cache
- release snapshot structure
- contract change event consumer
- cache invalidation flow
- request-level version pinning

완료 기준:
- 동일 요청 흐름에서 같은 semantic release가 유지됨
- 계약 변경 시 stale cache가 자동 정리됨

### Sprint 4 — Semantic Retrieval Enrichment
목표: 질문 해석 단계에서 ontology를 실제 활용하기

구현 항목:
- ontology synonym expansion
- term normalization
- intent confidence scoring
- context pack reranking
- fallback policy refinement

완료 기준:
- synonym 기반 질문 확장이 동작함
- intent confidence가 낮을 때 안전 모드로 전환 가능

---

## 10. 최종 결론

현재 구현은 실패한 상태가 아니다. 오히려 **시맨틱 플랫폼의 핵심 골격은 상당히 잘 세워진 상태**다.  
문제는 이제 “더 많은 정의를 추가하는 것”이 아니라, **이미 정의된 의미를 실제 실행 시점에 강제하고, 품질과 일관성을 소비자 경험에 연결하는 것**이다.

따라서 다음 단계의 본질은 확장보다 보강이다.

- 테이블을 더 만드는 것보다
- 의미 검증을 붙이고
- 품질 기반 행동 제어를 넣고
- release 일관성을 보장하는 것

이 3가지를 먼저 닫아야 한다.

그 이후에야 domain federation, ML feature integration, advanced policy/rule layer가 의미를 가진다.

---

## 11. 최종 한줄 평가

> **지금의 Axiom은 ‘잘 만든 Semantic Control Plane’이다. 다음 목표는 그것을 ‘신뢰 가능한 Semantic Enforcement Runtime’으로 완성하는 것이다.**
