# Axiom 통합 스프린트 백로그 (Master)

## 1. 운영 원칙
- 스프린트 길이: 2주
- 완료 정의(DoD): 코드 + 테스트 + 문서 + Gate 체크리스트 충족
- 품질게이트: `lint + type + unit + integration + security` 필수
- 계약 우선: API/OpenAPI 변경은 구현 전 승인

## 2. 프로그램 스프린트 로드맵

### Sprint 1 (Foundation)
- 목표: SSOT/경계/공통 규칙 고정
- 범위: Core 00/01/02, Synapse 01, Oracle 01, Canvas 01
- 핵심 산출물:
  - 서비스 경계 고정 문서/검증 스크립트
  - 공통 에러 모델/권한 모델/포트 SSOT 적용
- 통과 기준:
  - 아키텍처 경계 위반 0건
  - 계약 변경 승인 프로세스 동작 확인

### Sprint 2 (Core Runtime)
- 목표: Core 프로세스/이벤트/보안 런타임 안정화
- 범위: Core 02/03/06/07/08
- 핵심 산출물:
  - 프로세스/워크아이템 상태전이 회귀 테스트
  - Outbox->Streams 멱등성 검증
  - 멀티테넌트 격리 검증 리포트
- 통과 기준:
  - Core Gate C1/C2 주요 항목 통과

### Sprint 3 (Graph Platform)
- 목표: Synapse + Weaver 그래프/메타데이터 기반 완성
- 범위: Synapse 02/03/06, Weaver 02/03/06/07
- 핵심 산출물:
  - 온톨로지/그래프 API 계약 테스트
  - metadata ingest/propagation 정합성 테스트
  - 4-Source Ingestion 계보 필드(`source_family/source_ref`) 저장 검증
- 통과 기준:
  - Synapse/Weaver Gate S1/W1 통과

### Sprint 4 (Oracle Intelligence)
- 목표: Oracle NL2SQL/품질게이트/보안 정책 구현
- 범위: Oracle 02/03/05/06/07
- 핵심 산출물:
  - SQL Guard + Quality Gate + Value Mapping 파이프라인
  - Synapse API 경유 그래프 검색/캐시 반영
- 통과 기준:
  - Oracle Gate O1/O2/O3 통과

### Sprint 5 (Vision Analytics)
- 목표: Vision 엔진(OLAP/What-if) API 안정화
- 범위: Vision 02/03/05/06/08
- 핵심 산출물:
  - 분석 API 계약 테스트 + 비동기 실행 안정화
  - ETL/MV 갱신 및 성능 검증
  - What-if 질문 템플릿(골든퀘션) 카탈로그 초안
- 통과 기준:
  - Vision Gate V1/V2 주요 항목 통과

### Sprint 6 (Canvas Integration)
- 목표: Canvas 기능 통합 및 E2E 안정화
- 범위: Canvas 02/03/04/06/07/08
- 핵심 산출물:
  - 핵심 사용자 여정 E2E 세트
  - 실시간 알림/협업/분석 연동 검증
- 통과 기준:
  - Canvas Gate U1/U2/U3 통과

### Sprint 7 (Hardening)
- 목표: 전 프로젝트 보안/성능/운영 하드닝
- 범위: 전 프로젝트 07/08/99
- 핵심 산출물:
  - 침투/부하/복구 리허설 결과
  - ADR 재평가 트리거 점검
  - Early Warning 폐루프 SLA(`detect->RCA->notify->resolve`) 검증 리포트
- 통과 기준:
  - Critical/High 취약점 0
  - 운영 리허설 완료

## 3. 크로스 의존성 차단 규칙
- Oracle은 Synapse API 가용 전 독립 완료로 인정하지 않음
- Canvas E2E 완료는 Core/Oracle/Synapse/Vision/Weaver 계약 테스트 통과가 선행
- ADR 변경은 해당 스프린트 시작 전에 `99_decisions` 반영 필수

## 4. 리스크 버퍼
- 스프린트당 20% 버퍼(계약 변경/데이터 이슈/성능 회귀)
- 운영 리스크(배포/롤백)는 Sprint 7 이전에 최소 1회 예행
