# CORE 06_data 데이터 모델 구현 계획

## 1. 문서 목적
- core 프로젝트의 06_data 설계 문서를 실제 구현 백로그로 변환한다.
- 단계별 책임 에이전트와 통과 기준을 명확히 정의한다.

## 2. 참조 설계 문서
- services/core/docs/06_data/data-lifecycle.md
- services/core/docs/06_data/database-operations.md
- services/core/docs/06_data/database-schema.md
- services/core/docs/06_data/event-outbox.md

## 3. 에이전트 운영
- 주관: backend-developer | 협업: code-security-auditor, code-inspector-tester
- 공통 점검: code-inspector-tester(테스트 완결성), code-standards-enforcer(품질게이트), code-documenter(문서 동기화)

## 4. 구현 작업 패키지
1. 스키마/인덱스/제약조건/파티셔닝 설계 구현 순서 수립
2. 데이터 생명주기(생성-갱신-보존-삭제) 정책 반영
3. 마이그레이션/이관/롤백 전략과 무결성 검증 계획 수립
4. 이벤트/그래프/캐시 모델 간 정합성 규칙 확정
5. 데이터 품질 지표와 정기 검증 배치 정의

## 5. 통과 기준 (Gate 06)
- 무결성 제약 위반 0건
- 마이그레이션 드라이런/롤백 리허설 완료
- 핵심 조회 성능 목표(p95) 충족

## 6. 산출물
- 구현 PR(코드 + 테스트 + 문서)
- 변경 영향 리포트(호환성/성능/보안)
- 운영 체크리스트 업데이트(필요 시)
