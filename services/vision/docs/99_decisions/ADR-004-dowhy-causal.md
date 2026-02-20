# ADR-004: DoWhy 인과 추론 라이브러리 선택

## 상태

Accepted

## 배경

See-Why 근본원인 분석 엔진에서 비즈니스 실패 원인의 인과 관계를 추론하기 위한 라이브러리를 선택해야 한다. 관측 데이터로부터 인과 구조를 발견하고, 인과 효과를 추정하며, 반사실 시나리오를 생성하는 기능이 필요하다.

### 요구사항

- 관측 데이터에서 인과 구조 발견 (Causal Discovery)
- 인과 효과 추정 (Causal Effect Estimation)
- 반사실 분석 (Counterfactual Reasoning)
- 인과 추정의 강건성 검증 (Refutation Tests)
- Python 네이티브
- 학술적으로 검증된 알고리즘

## 고려한 옵션

### 1. DoWhy (Microsoft Research)

- **장점**: 4단계 인과 추론 프레임워크(모델→식별→추정→검증), 다양한 추정 방법(백도어, 도구변수, DML), Refutation test 내장, 활발한 개발, Microsoft Research 유지보수, 반사실 분석 지원
- **단점**: 인과 그래프를 사전에 정의해야 함 (자동 발견은 별도 라이브러리 필요), 대규모 데이터에서 느릴 수 있음

### 2. CausalNex (QuantumBlack/McKinsey)

- **장점**: 베이지안 네트워크 기반, 시각화 내장, McKinsey 유지보수
- **단점**: DoWhy 대비 추정 방법 제한, Refutation test 미지원, 반사실 분석 미지원, 업데이트 빈도 낮음

### 3. causal-learn (CMU)

- **장점**: Causal Discovery 알고리즘 풍부 (PC, FCI, GES, LiNGAM), 학술적으로 가장 신뢰
- **단점**: Discovery만 지원 (Effect Estimation, Counterfactual 미지원), DoWhy와 조합 필요

### 4. pgmpy (Probabilistic Graphical Models)

- **장점**: 베이지안 네트워크 + 인과 추론, 범용적
- **단점**: 인과 추론 특화가 아닌 범용 확률 모델, 반사실 분석 미지원

### 5. EconML (Microsoft Research)

- **장점**: 이중 기계학습(DML) 기반 인과 효과 추정, 이질적 처치 효과(HTE) 분석
- **단점**: 인과 구조 발견 미지원, DoWhy의 추정 백엔드로 활용 가능

## 선택한 결정

**DoWhy + causal-learn (조합)**

- DoWhy: 인과 효과 추정 + 반사실 분석 + 검증
- causal-learn: 인과 구조 발견 (PC Algorithm, LiNGAM)

## 근거

1. **완전한 인과 추론 파이프라인**: causal-learn의 PC Algorithm + LiNGAM으로 인과 구조를 발견하고, DoWhy로 인과 효과를 추정하며, DoWhy의 Refutation test로 검증하는 완전한 파이프라인 구성 가능.

2. **Refutation Test**: DoWhy만이 내장 검증(placebo treatment, random common cause, data subset)을 제공. 비즈니스 도메인에서 "이 인과 관계가 정말 맞는가?"를 통계적으로 검증할 수 있음.

3. **반사실 분석**: "부채비율이 40%였다면?" 같은 반사실 질의를 DoWhy가 직접 지원. 분석 보고서에서 핵심적인 분석.

4. **학술적 신뢰도**: DoWhy(Microsoft Research)와 causal-learn(CMU)은 모두 학술 논문으로 검증된 라이브러리. 공식 보고서에 사용할 분석의 신뢰도 확보.

5. **확장성**: DoWhy는 EconML을 추정 백엔드로 사용 가능하므로, 향후 더 정교한 추정 방법으로 확장 가능.

## 결과

### 긍정적 영향

- 인과 발견 → 추정 → 검증 → 반사실의 완전한 파이프라인
- 공식 보고서에 사용 가능한 수준의 통계적 검증
- "왜 실패했는가?"에 대한 데이터 기반 답변 제공

### 부정적 영향

- 학습 데이터 최소 100건 필요 (Phase 4 전제조건)
- 인과 그래프 구축에 도메인 전문가 HITL 필요
- 두 라이브러리 의존성 관리 (DoWhy + causal-learn)
- ML 모델 학습/배포 인프라 필요

## 재평가 조건

- 시계열 인과 추론이 필요할 때 (Granger Causality, VAR 모델 검토)
- 비정형 데이터(텍스트)에서 인과 관계 추출이 필요할 때
- 실시간 인과 추론이 필요할 때
- 인과 그래프 노드가 50개 이상으로 복잡해질 때

---

## 증거

- 01_architecture/root-cause-engine.md (인과 추론 파이프라인)
- 05_llm/causal-explanation.md (LLM 설명 생성)
- K-AIR WorkFlowy "See-why 원인분석" 설계 참조
