# SYNAPSE 99_decisions ADR/의사결정 반영 계획

## 1. 문서 목적
- synapse 프로젝트의 99_decisions 설계 문서를 실제 구현 백로그로 변환한다.
- 단계별 책임 에이전트와 통과 기준을 명확히 정의한다.

## 2. 참조 설계 문서
- services/synapse/docs/99_decisions/ADR-001-neo4j-graph.md
- services/synapse/docs/99_decisions/ADR-002-4layer-ontology.md
- services/synapse/docs/99_decisions/ADR-003-gpt4o-extraction.md
- services/synapse/docs/99_decisions/ADR-004-hitl-threshold.md
- services/synapse/docs/99_decisions/ADR-005-pm4py-process-mining.md

## 3. 에이전트 운영
- 주관: technical-doc-writer, code-implementation-planner | 협업: code-reviewer
- 공통 점검: code-inspector-tester(테스트 완결성), code-standards-enforcer(품질게이트), code-documenter(문서 동기화)

## 4. 구현 작업 패키지
1. ADR별 구현 영향 범위와 코드 변경 포인트 연결
2. 상충 ADR 탐지 및 우선순위/대체안 정리
3. 재평가 조건 트리거를 운영 지표로 매핑
4. 브레이킹 결정의 마이그레이션 경로 정의
5. 결정-사실 분리 원칙으로 문서 최신화 계획 수립

## 5. 통과 기준 (Gate 99)
- ADR별 구현 항목 추적 가능(링크/ID)
- 상충 결정 미해결 항목 0건
- 재평가 트리거/책임자/주기 명시 완료

## 6. 산출물
- 구현 PR(코드 + 테스트 + 문서)
- 변경 영향 리포트(호환성/성능/보안)
- 운영 체크리스트 업데이트(필요 시)
