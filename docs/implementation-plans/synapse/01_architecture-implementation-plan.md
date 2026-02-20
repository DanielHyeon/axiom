# SYNAPSE 01_architecture 아키텍처 구현 계획

## 1. 문서 목적
- synapse 프로젝트의 01_architecture 설계 문서를 실제 구현 백로그로 변환한다.
- 단계별 책임 에이전트와 통과 기준을 명확히 정의한다.

## 2. 참조 설계 문서
- services/synapse/docs/01_architecture/architecture-overview.md
- services/synapse/docs/01_architecture/extraction-pipeline.md
- services/synapse/docs/01_architecture/graph-search.md
- services/synapse/docs/01_architecture/ontology-4layer.md
- services/synapse/docs/01_architecture/process-mining-engine.md
- services/synapse/docs/01_architecture/code-archaeology-pipeline.md
- services/synapse/docs/01_architecture/audio-ingestion-pipeline.md
- docs/architecture-4source-ingestion.md
- docs/domain-contract-registry.md

## 3. 에이전트 운영
- 주관: code-implementation-planner, backend-developer | 협업: code-refactor, code-reviewer
- 공통 점검: code-inspector-tester(테스트 완결성), code-standards-enforcer(품질게이트), code-documenter(문서 동기화)

## 4. 구현 작업 패키지
1. 아키텍처 경계(레이어/모듈/의존방향) 코드 규칙화
2. 핵심 시나리오별 컴포넌트 책임 할당
3. 장애 격리/복원력 패턴(CB/Retry/Timeout/Fallback) 구현 계획 수립
4. 동기/비동기 경계와 트랜잭션 경계 확정
5. ADR 반영 순서와 브레이킹 체인지 승인 흐름 고정

## 5. 통과 기준 (Gate 01)
- 금지 의존(역방향 import, 우회 호출) 0건
- 핵심 시퀀스별 책임 컴포넌트가 단일화됨
- ADR와 구현 계획 간 충돌 0건

## 6. 산출물
- 구현 PR(코드 + 테스트 + 문서)
- 변경 영향 리포트(호환성/성능/보안)
- 운영 체크리스트 업데이트(필요 시)
