# Research 반영 점검 리포트 (2026-02-20)

## 1. 범위
- 입력 자료
  - `research/The_Enterprise_World_Model_Blueprint.pdf` (13p)
  - `research/Autonomous_AI_Agent_Mesh_cropped_logo.pdf` (15p)
  - `research/차세대 AI 아키텍처_ 자율형 에이전트 메시와 엔터프라이즈 월드 모델_v2.pdf` (62p)
  - `research/질문으로_설계하는_기업_예측_월드_모델.m4a` (14m46s)
- 대조 대상
  - 설계 문서: `docs/`, `services/*/docs`, `apps/canvas/docs`
  - 구현 계획: `docs/03_implementation/*`

## 2. 분석 방법
- PDF는 이미지 기반 문서이므로 페이지 렌더링 후 시각 판독으로 핵심 요구사항 추출.
- 추출한 요구사항을 현재 설계/계획 문서에 키워드/근거 라인 단위로 매핑.
- 반영 수준을 `반영`, `부분 반영`, `미반영`으로 분류.

## 3. 기술적 한계
- `m4a` 음성은 현재 로컬 환경에 STT 도구(`whisper`, `faster-whisper`, `vosk`, `ffmpeg`)가 없어 내용 전사를 수행하지 못함.
- 본 리포트는 PDF 2종 + 기존 연구 문서(`research/k-air-reverse-engineering-analysis.md`)를 중심으로 평가함.

## 4. PDF 핵심 요구사항 요약
- 월드 모델/디지털 트윈 기반의 의미 계층(Semantic Layer) 구축
- 레거시 코드/문서/외부 레퍼런스 융합 후 도메인 모델 추출
- DDD 개념(aggregate, invariant, policy, event)을 온톨로지에 매핑
- Event-Driven 루프(command -> state change -> event publish -> policy trigger)
- What-if + Root Cause 기반 예측/원인 분석
- HITL 기반 검증(자가 검증 후 전문가 보정)
- 실시간 모니터링/알림(Watch)
- Data Mesh 추상화(하부 레거시 DB 은닉)
- Local Agent + Global Agent 오케스트레이션/거버넌스
- LLM 기반 Generate -> Operate -> Learn 플라이휠

## 5. 반영 현황

### 5.1 반영됨 (설계 + 구현계획 정합)
1. Semantic Layer + Legacy 불변 원칙
- `docs/01_architecture/semantic-layer.md:1`
- `docs/01_architecture/semantic-layer.md:8`
- `docs/06_governance/legacy-data-isolation-policy.md:1`
- `docs/06_governance/legacy-data-isolation-policy.md:7`

2. 4계층 온톨로지 + EventStorming 매핑
- `services/synapse/docs/99_decisions/ADR-002-4layer-ontology.md:1`
- `services/synapse/docs/99_decisions/ADR-002-4layer-ontology.md:11`
- `services/synapse/docs/01_architecture/ontology-4layer.md:44`
- `services/synapse/docs/01_architecture/architecture-overview.md:192`
- `docs/03_implementation/synapse/98_gate-pass-criteria.md:5`

3. 비정형 -> 온톨로지 추출 + HITL 임계값
- `services/synapse/docs/02_api/extraction-api.md:1`
- `services/synapse/docs/02_api/extraction-api.md:29`
- `services/synapse/docs/99_decisions/ADR-004-hitl-threshold.md:1`
- `services/synapse/docs/99_decisions/ADR-004-hitl-threshold.md:81`
- `docs/03_implementation/synapse/98_gate-pass-criteria.md:10`

4. What-if / Root-Cause 분석 축
- `services/vision/docs/01_architecture/what-if-engine.md:1`
- `services/vision/docs/02_api/what-if-api.md:1`
- `services/vision/docs/01_architecture/root-cause-engine.md:1`
- `services/vision/docs/02_api/root-cause-api.md:1`
- `services/vision/docs/00_overview/system-overview.md:69`
- `services/vision/docs/00_overview/system-overview.md:104`

5. Watch Agent + CEP + 실시간 알림
- `services/core/docs/00_overview/system-overview.md:42`
- `services/core/docs/01_architecture/event-driven.md:448`
- `services/core/docs/02_api/watch-api.md:1`
- `services/core/docs/02_api/watch-api.md:26`
- `docs/03_implementation/core/98_gate-pass-criteria.md:11`

6. Data Fabric(MindsDB) + 메타데이터 SSOT
- `services/weaver/docs/99_decisions/ADR-001-mindsdb-gateway.md:1`
- `services/weaver/docs/01_architecture/metadata-service.md:24`
- `services/weaver/docs/99_decisions/ADR-004-metadata-service.md:112`
- `docs/03_implementation/weaver/01_architecture-implementation-plan.md:26`

### 5.2 부분 반영 (개념은 있으나 구현/운영 정의가 약함)
1. DDD 추출 자동화 (레거시 코드 -> aggregate/invariant/policy 자동 발굴)
- 현재는 EventStorming/온톨로지 매핑은 존재하나, 정적 코드 분석 파이프라인/규칙 엔진은 문서화가 약함.
- 근거: 온톨로지/이벤트 매핑 중심 문서 다수 vs 코드 아키올로지 자동화 문서 부재.

2. Event-Driven 도메인 표준계약(명시적 Command/Event/Policy 스키마 레지스트리)
- Watch CEP/이벤트버스는 강함.
- 하지만 PDF가 강조한 "도메인 이벤트 표준 단위" 관점의 registry/versioning/governance 문서가 서비스 공통 표준으로는 약함.

3. Local Agent/Global Agent 2계층 운영 모델
- Core 오케스트레이션/에이전트 아키텍처는 존재.
- 하지만 "로컬 에이전트 집합 + 글로벌 에이전트 거버넌스"를 별도 계층 모델로 정의한 문서/통과기준은 약함.
- `docs/03_implementation/program/09_agent-governance-and-acceptance.md`는 운영 RACI 중심.

4. Generate -> Operate -> Learn 플라이휠의 제품 KPI
- 학습/피드백 요소는 존재 (`knowledge-management`, HITL, 로그/모니터링).
- 그러나 모델 진화 루프를 제품 KPI(학습 속도, 승인율 개선, 오탐 감소율)로 묶은 전사 기준은 약함.

### 5.3 미반영 또는 명시 부족
1. Golden Question(질문 기반 필터) 공식 방법론
- 설계 철학으로는 유사 개념이 있으나, 표준 입력 템플릿/품질 게이트로 고정되지 않음.

2. Self-Verification 20% 규칙의 시스템 테스트 규약
- Canvas UX에서 80/20 HITL 철학은 존재 (`apps/canvas/docs/04_frontend/ux-interaction-patterns.md:109`).
- 그러나 모델 자체 self-check(샘플링 검증) 파이프라인은 독립 모듈/수치 기준으로 분리되어 있지 않음.

3. 음성/회의록 기반 온톨로지 추출 표준
- 문서 추출은 강하지만, 음성 입력(ASR -> ontology) 파이프라인은 문서화/계획에 없음.

## 6. 추가 구현 권고 (우선순위)

### [High] R1. Domain Contract Registry 신설
- 목적: Command/Event/Policy/Invariant를 서비스 공통 스키마로 버전 관리.
- 산출물:
  - `docs/06_governance/domain-contract-registry.md` (신규)
  - Core/Synapse/Vision 이벤트 타입 매핑표
  - breaking-change 승인 규칙
- 통과 기준:
  - 핵심 이벤트 100%에 `owner/version/payload_schema/idempotency_key` 존재
  - 서비스 간 이벤트 계약 충돌 0건

### [High] R2. Legacy Code -> DDD 추출 파이프라인 정의
- 목적: 레거시 코드/DDL에서 aggregate/invariant/policy를 반자동 추출.
- 산출물:
  - Synapse 또는 Core에 `code-archaeology` 설계 문서
  - 추출 결과를 `ontology/eventstorming` 입력으로 연결
- 통과 기준:
  - 샘플 레거시 3개 시스템에서 aggregate 후보 자동 추출 재현
  - HITL 승인율/정확도 리포트 제공

### [Medium] R3. Agent Layer Model (Local/Global) 명시화
- 목적: 로컬 에이전트와 글로벌 오케스트레이터의 책임/권한 경계 고정.
- 산출물:
  - `services/core/docs/01_architecture/agent-layering.md` (신규)
  - 프로그램 게이트에 orchestration/choreography/governance 체크 추가
- 통과 기준:
  - 로컬/글로벌 간 호출 경계 위반 0건
  - 장애 시 글로벌 에이전트 fail-safe 시나리오 검증

### [Medium] R4. Self-Verification Harness 도입
- 목적: 모델 결과를 런타임 전 자동 자기검증.
- 산출물:
  - 20% 샘플링 self-check 정책(케이스 유형별)
  - 오탐/누락 회귀 테스트 배치
- 통과 기준:
  - self-check 통과율/오탐률/재검토율이 대시보드에서 추적 가능
  - 미통과 결과는 자동 HITL 큐로 라우팅

### [Low] R5. Voice-to-Ontology 확장
- 목적: 회의 음성 -> 전사 -> 개체/관계 추출 -> HITL.
- 산출물:
  - `audio-ingestion` API/워커 설계
  - 개인정보/보안 마스킹 정책
- 통과 기준:
  - 30분 이내 음성 파일 처리 SLA
  - 엔티티 추출 precision/recall 목표 정의

## 7. 결론
- PDF 3종의 핵심 방향(시맨틱 레이어, 온톨로지, What-if, Root Cause, Watch, Data Mesh)은 현재 Axiom 설계/구현계획에 높은 수준으로 반영되어 있다.
- 다만 "자율 에이전트 메시" 관점의 운영 완성도를 높이려면, `도메인 이벤트 계약 레지스트리`, `레거시 코드 DDD 추출 자동화`, `로컬/글로벌 에이전트 계층 명시`, `self-verification 하네스`를 다음 우선순위로 보강하는 것이 필요하다.

## 8. v2 PDF 추가 반영 점검 (Delta)

### 8.1 새롭게 확인된 핵심 요구
- 4가지 데이터 소스 전략의 명시: DB, 레거시 코드, 공식 문서(SOP/규정), 산업 표준 온톨로지
- 글로벌 에이전트의 3대 책임 명시: Orchestration / Choreography / Governance
- Early Warning 운영체계 명시: `Critical/Warning/Info` 등급 + 자동 대응 루프(이상 감지 -> RCA -> 팀 알림 -> 대응 실행)
- What-if/RCA의 실무 KPI 중심 시나리오 강조(배송, CSAT, 지연 클레임, 매출 영향)
- Generate/Operate/Learn 플라이휠을 운영전략으로 반복 강조

### 8.2 기존 평가와의 정합성
- 기존 리포트의 핵심 결론(반영 높음 + 운영 거버넌스 보강 필요)은 v2 확인 후에도 유지된다.
- v2가 강조한 항목 다수는 이미 부분 반영되어 있음:
  - 글로벌 에이전트/거버넌스: Core 오케스트레이션 문서와 Program 거버넌스 문서 존재
  - Early Warning 등급: Watch/Monitoring 문서에서 severity 체계 확인
  - 규정/레퍼런스: Synapse 엔티티 추출(`REGULATION/REFERENCE`) 및 Weaver 감사/규정준수 스냅샷 정책 존재

### 8.3 v2 기준 추가 보강 포인트
1. [High] 4-Source Ingestion 표준화
- DB/Code/Docs/External Ontology를 하나의 공통 파이프라인 규약으로 문서화 필요
- 현재는 모듈별 문서에 분산되어 있어 프로그램 레벨 운영표준이 약함

2. [Medium] Early Warning 액션 런북 표준
- `Critical/Warning/Info`는 존재하나, "알림 -> RCA -> 부서 통보 -> 조치 완료"의 업무 폐루프 SLA를 서비스 공통으로 고정할 필요

3. [Medium] 시뮬레이션 카탈로그
- v2는 도메인형 What-if 질문 템플릿을 강조하므로, 산업별 질문 템플릿 라이브러리(골든 퀘션 포함)를 운영 자산으로 별도 관리 필요
