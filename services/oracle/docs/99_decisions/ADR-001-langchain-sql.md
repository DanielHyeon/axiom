# ADR-001: LangChain 기반 SQL 생성 선택

## 상태

Accepted

## 배경

Oracle 모듈은 자연어 질문을 SQL로 변환해야 한다. SQL 생성 방식을 선택해야 하며, 주요 후보는 다음과 같다:

1. **LangChain SQL Chain**: LangChain의 구조화된 체인/에이전트 프레임워크
2. **직접 OpenAI API 호출**: 프롬프트를 직접 구성하고 API 호출
3. **LlamaIndex SQL**: LlamaIndex의 SQL 쿼리 엔진
4. **DSPy**: 자동 프롬프트 최적화 프레임워크

K-AIR `robo-data-text2sql-main`은 LangChain을 사용하고 있으며, 95% 구현 완성도로 운영 검증된 코드 베이스이다.

## 고려한 옵션

### 옵션 A: LangChain SQL Chain

**장점**:
- K-AIR 검증된 코드 그대로 이식 가능
- 프롬프트 체인, 출력 파서, 메모리 등 풍부한 추상화
- ReAct 에이전트 구현이 내장
- 활발한 커뮤니티와 문서
- LLM 프로바이더 교체 용이

**단점**:
- 프레임워크 종속성 (버전 업데이트 시 breaking change 가능)
- 추상화 계층이 디버깅을 어렵게 할 수 있음
- 간단한 작업에도 프레임워크 오버헤드 존재

### 옵션 B: 직접 OpenAI API 호출

**장점**:
- 외부 의존성 최소
- 완전한 제어 가능
- 디버깅 용이

**단점**:
- 프롬프트 관리, 재시도, 스트리밍 등을 직접 구현해야 함
- ReAct 패턴 직접 구현 필요
- K-AIR 코드 재사용 불가

### 옵션 C: LlamaIndex SQL

**장점**:
- SQL 쿼리에 특화된 설계
- 스키마 연동 기능 내장

**단점**:
- K-AIR 코드 재사용 불가
- Synapse Graph API 연동 생태계가 LangChain보다 약함
- 커뮤니티 규모가 작음

### 옵션 D: DSPy

**장점**:
- 자동 프롬프트 최적화
- 학술적으로 검증된 접근

**단점**:
- 실험적 단계
- 운영 환경 검증 사례 부족
- K-AIR 코드 재사용 불가

## 선택한 결정

**옵션 A: LangChain SQL Chain**

## 근거

1. **이식 비용 최소화**: K-AIR의 95% 구현 완성도를 가진 LangChain 기반 코드를 그대로 이식 가능. 프레임워크 변경 시 전체 재작성이 필요하며, 이는 2~3주 추가 개발을 의미
2. **운영 검증**: K-AIR에서 실제 운영 데이터로 동작한 검증된 코드
3. **ReAct 에이전트 지원**: 다단계 추론 패턴이 LangChain에 내장되어 있어 별도 구현 불필요
4. **그래프 연동 유연성**: LangChain의 도구/체인 구성으로 Synapse Graph API 어댑터를 안정적으로 구성 가능
5. **LLM 교체 유연성**: LLM 프로바이더를 설정으로 교체 가능

## 결과

### 긍정적 영향

- K-AIR 이식 기간 단축 (2~3주 절약)
- 검증된 파이프라인 구조 재활용
- LangChain 생태계의 새로운 기능(LangSmith 모니터링 등) 활용 가능

### 부정적 영향

- LangChain 버전 업데이트 시 breaking change 대응 필요
- 프레임워크 내부 동작 디버깅 어려움 (추상화 계층)
- LangChain 의존성 크기 (설치 패키지 수)

### 완화 전략

- LangChain 버전을 고정하고 주요 버전 업그레이드 시 테스트 수행
- 코어 로직(SQL Guard, 그래프 검색 등)은 LangChain에 의존하지 않도록 설계
- LLM 호출은 LLM Factory로 추상화하여 LangChain 없이도 동작 가능하게

## 재평가 조건

- LangChain 2.0 등 주요 버전 변경으로 마이그레이션 비용이 높아질 때
- 직접 API 호출로도 충분히 단순한 파이프라인임이 증명될 때
- DSPy 등 대안 프레임워크가 운영 수준으로 성숙할 때

---

**근거 문서**: [00_overview/system-overview.md](../00_overview/system-overview.md)
**영향 문서**: [05_llm/prompt-engineering.md](../05_llm/prompt-engineering.md), [05_llm/react-agent.md](../05_llm/react-agent.md)
