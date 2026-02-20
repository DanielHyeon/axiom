# Self-Verification Harness (자기 검증 체계)

## 1. 목적
- 언어 모델(LLM) 및 에이전트가 생성한 추론 결과나 변경 사항이 런타임에 직접 반영되기 전, 시스템 스스로 규칙을 검증하여 오작동(Hallucination/Omission)을 차단한다.
- HITL(Human-In-The-Loop) 검토 이전에 자동 검증망을 구성하여 전문가 피로도를 감소시킨다.

## 2. 20% 랜덤 샘플링 Self-Check 정책
본 시스템은 모든 결과물을 검증하는 것이 원칙이나, 자원 한계와 병목을 방지하기 위해 다음 원칙을 적용한다.

- **High-Risk Case (100% 검증)**: 결제 통제, 권한 부여, 주요 Ontology Node/Relation 삭제 등 파급력이 큰 작업은 100% 자동 Self-Check 및 100% HITL 승인을 거친다.
- **Medium/Low-Risk Case (20% 샘플링 검증)**: 비정형 데이터 단순 추출, 로그 요약, 도메인 이벤트 로깅은 전체 응답의 20%를 무작위 추출하여 Self-Verification Validator(별도의 비평가/판사 에이전트 모델)에 회부한다.

## 3. 회귀 테스트 배치 체계 (Regression Test Batch)
- 오탐(False Positives) 및 누락(Omission) 데이터를 주 단위로 수집하여 Golden QA Set으로 축적한다.
- 매 릴리스 파이프라인(CI/CD)에서는 이 축적된 테스트셋을 바탕으로 에이전트 품질이 회귀하지 않았음을 보장해야 한다.

## 4. 피드백 루프 (Fail Routing)
- Self-check 결과 "Fail" 또는 "Low Confidence(임계치 미달)" 판정을 받은 결과물은 자동 반영 큐에서 즉시 추방된다.
- 이 추방된 데이터는 곧바로 HITL 워크스테이션 대기열로 라우팅되어 사람의 직접 교정을 유도한다.
- 교정된 결과 내역은 다시 Knowledge Graph와 Self-Verification Validator의 Few-Shot 프롬프트로 역기여(Feedback Loop)된다.

## 5. 통과 기준 (Pass Criteria)
- 런타임 검증을 통해 Self-check 통과율, 오탐률, 인간 재검토(HITL Routing)율이 운영 대시보드(Watch Agent)에 실시간 추적 가능해야 한다.
- 누적된 Golden QA Set 기반 배치 테스트 시, 이전 버전에 통과한 Test Case가 실패 처리되는 등급별 회귀가 0건이어야 한다.
