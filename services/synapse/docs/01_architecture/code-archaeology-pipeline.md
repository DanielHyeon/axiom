# Legacy Code to DDD Extraction Pipeline (Code Archaeology)

## 1. 목적
- 기존 레거시 시스템의 코드베이스와 DDL을 정적/동적으로 분석하여, Domain-Driven Design(DDD) 패턴인 Aggregate, Invariant, Policy를 반자동으로 추출한다.
- 추출된 도메인 지식은 시맨틱 레이어(Synapse Ontology)와 EventStorming 모델의 공식 입력 소스로 활용된다.

## 2. 아키텍처 개요
본 파이프라인은 3단계(Ingestion, Analysis, Mapping)로 구성된다.

### 2.1 단계별 파이프라인 구조
1. **코드 수집 및 파싱 (Ingestion & Parsing)**
   - **입력**: 레거시 Git Repository, DB DDL/Schema Snapshot
   - **처리**: AST(Abstract Syntax Tree) 파싱, 정적 제어 흐름 및 데이터 흐름 그래프(DFG) 생성
2. **패턴 매칭 및 규칙 엔진 (Analysis Engine)**
   - **규칙 엔진**: 특정 클래스/테이블 응집도, 트랜잭션 경계, 예외 처리 패턴을 감지하여 도메인 객체(Aggregate 후보) 식별
   - **LLM 보조 분석**: 변수명, 주석, 로직 맥락을 기반으로 숨겨진 비즈니스 규칙(Invariant, Policy) 의도 시맨틱 추출
3. **온톨로지 및 이벤트 매핑 (Mapping & Export)**
   - 추출된 Aggregate 구조와 Policy를 Synapse의 4-Layer Ontology(Process/Resource) 구조에 맞게 변환
   - 식별된 이벤트를 EventStorming 포맷에 맞게 내보내기

## 3. Synapse 온톨로지 연계 (Ingestion Flow)
- 추출 파이프라인 산출물은 `synapse-ontology-worker`의 입력으로 주입된다.
- **연결 고리**: 추출된 Aggregate는 온톨로지의 `Resource` 노드로, 추출된 Policy/Invariant 로직은 노드 간 `Relation` 제약 조건으로 매핑된다.
- 자동 추출 결과는 신뢰도(Confidence Score)를 가지며, 임계값(예: 80%) 미만 개체는 곧바로 DB에 반영하지 않고 HITL(Human-In-The-Loop) 검토 대기열로 라우팅된다.

## 4. 통과 기준 (Pass Criteria)
- 3개의 샘플 레거시 시스템(예: 상품, 결제, 회원)에서 Aggregate 후보를 자동으로 추출 및 재현 가능 여부 입증
- 도출된 Aggregate 및 Policy의 정답 셋 대비 정확도 리포트 산출
- HITL 검토 대기열에 쌓인 추출 내역에 대한 전문가 승인율(Approval Rate) 지표 대시보드 제공
