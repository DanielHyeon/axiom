# WEAVER 06_data 데이터 모델 구현 계획

## 1. 문서 목적
- weaver 프로젝트의 06_data 설계 문서를 실제 구현 백로그로 변환한다.
- 단계별 책임 에이전트와 통과 기준을 명확히 정의한다.

## 2. 참조 설계 문서
- services/weaver/docs/06_data/data-flow.md
- services/weaver/docs/06_data/datasource-config.md
- services/weaver/docs/06_data/neo4j-schema-v2.md
- services/weaver/docs/06_data/neo4j-schema.md
- docs/01_architecture/semantic-layer.md
- docs/06_governance/legacy-data-isolation-policy.md

## 3. 에이전트 운영
- 주관: backend-developer | 협업: code-security-auditor, code-inspector-tester
- 공통 점검: code-inspector-tester(테스트 완결성), code-standards-enforcer(품질게이트), code-documenter(문서 동기화)

## 4. 구현 작업 패키지
1. 스키마/인덱스/제약조건/파티셔닝 설계 구현 순서 수립
2. 데이터 생명주기(생성-갱신-보존-삭제) 정책 반영
3. 마이그레이션/이관/롤백 전략과 무결성 검증 계획 수립
4. 이벤트/그래프/캐시 모델 간 정합성 규칙 확정
5. 데이터 품질 지표와 정기 검증 배치 정의
6. `GlossaryTerm` 등 Planned/Experimental 스키마의 활성화 조건과 마이그레이션 타이밍 명시
7. Neo4j v2 노드의 계보 태그(`source_family`, `source_ref`)와 질문 필터 키(`golden_question_id`) 확장 설계
8. 공식 문서/규정/외부 참조를 메타데이터 레퍼런스로 연결하는 모델(`ReferenceSource`) 적용 여부 결정

## 5. 통과 기준 (Gate 06)
- 무결성 제약 위반 0건
- 마이그레이션 드라이런/롤백 리허설 완료
- 핵심 조회 성능 목표(p95) 충족
- 레거시 원본 DB 스키마 직접 변경 경로 0건
- 메타데이터 노드 계보 필드 누락률 0%
- 4-Source 분류( database / legacy_code / official_docs / external_reference ) 통계 조회 가능

## 6. 산출물
- 구현 PR(코드 + 테스트 + 문서)
- 변경 영향 리포트(호환성/성능/보안)
- 운영 체크리스트 업데이트(필요 시)
