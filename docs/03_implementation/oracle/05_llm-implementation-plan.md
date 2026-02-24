# ORACLE 05_llm LLM/에이전트 구현 계획

## 1. 문서 목적
- oracle 프로젝트의 05_llm 설계 문서를 실제 구현 백로그로 변환한다.
- 단계별 책임 에이전트와 통과 기준을 명확히 정의한다.

## 2. 참조 설계 문서
- services/oracle/docs/05_llm/llm-factory.md
- services/oracle/docs/05_llm/prompt-engineering.md
- services/oracle/docs/05_llm/react-agent.md
- services/oracle/docs/05_llm/visualization.md

## 3. 에이전트 운영
- 주관: backend-developer | 협업: api-developer, code-security-auditor, code-reviewer
- 공통 점검: code-inspector-tester(테스트 완결성), code-standards-enforcer(품질게이트), code-documenter(문서 동기화)

## 4. 구현 작업 패키지
1. 프롬프트/모델/도구 체인과 실패시 폴백 전략 확정
2. 구조화 출력 스키마 및 검증 파이프라인 설계
3. HITL 임계값/승인흐름/감사로그 체계 반영
4. 비용/지연/품질 지표와 캐시 전략 정의
5. 환각/권한오남용/프롬프트 인젝션 방지 통제 적용

## 5. 통과 기준 (Gate 05)
- 구조화 출력 파싱 실패율 목표치 이내
- HITL 경계값 기반 승인/거절 흐름 재현 가능
- 민감정보 노출/권한 우회 0건

## 6. 산출물
- 구현 PR(코드 + 테스트 + 문서)
- 변경 영향 리포트(호환성/성능/보안)
- 운영 체크리스트 업데이트(필요 시)
