# ADR-005: pm4py를 Process Mining 엔진으로 선택

## 상태

Accepted

## 배경

Axiom Synapse에 Process Mining 기능을 추가해야 한다. Business Process Intelligence 플랫폼으로서, EventStorming으로 설계된 프로세스 모델과 실제 이벤트 로그 간의 적합성 검사, 프로세스 자동 발견, 병목 탐지, 변종 분석 기능이 필요하다.

핵심 요구사항:
- Process Discovery: 이벤트 로그에서 프로세스 모델 자동 발견
- Conformance Checking: 설계 모델(EventStorming) vs 실행 로그 적합성 검사
- Variant Analysis: 프로세스 변종 식별 및 통계
- Bottleneck Detection: 활동별 소요시간 분석, 병목 탐지
- BPMN Export: 발견된 모델을 Canvas에서 시각화
- Python 기반: 기존 FastAPI 스택과 통합
- 이벤트 로그 형식: XES, CSV, DB 테이블 지원

## 검토한 옵션

### 옵션 1: pm4py

- Python 네이티브 오픈소스 Process Mining 라이브러리
- RWTH Aachen / Fraunhofer FIT에서 개발, 학술적으로 검증됨
- Alpha Miner, Heuristic Miner, Inductive Miner 내장
- Token-based replay Conformance Checking 내장
- BPMN 자동 생성 (`pm4py.discover_bpmn_inductive()`)
- Organizational Mining (리소스 프로파일, 소셜 네트워크)
- pip install pm4py로 즉시 사용 가능
- 라이선스: GPL-3.0 (오픈소스)

### 옵션 2: Celonis SDK (Python)

- 상용 Process Mining 플랫폼의 Python SDK
- 클라우드 기반, 강력한 시각화 내장
- 대규모 이벤트 로그 처리에 최적화
- 단점: 상용 라이선스 비용 (연 수천만원~), 클라우드 종속, 자체 호스팅 불가
- 단점: Celonis 플랫폼과 결합되어 Axiom Canvas 통합 어려움

### 옵션 3: 커스텀 구현

- 알고리즘을 직접 구현 (Python/Rust)
- 완전한 제어권
- 단점: 개발 기간 3-6개월 (Alpha Miner만 2-3주), 학술적 검증 부재
- 단점: Conformance Checking, BPMN Export 등 모두 직접 구현 필요

### 옵션 4: ProM (Java)

- 학술 분야의 표준 Process Mining 도구
- Java 기반, GUI 위주
- 가장 많은 알고리즘 플러그인 (100+)
- 단점: Java 기반으로 FastAPI(Python) 스택과 이질적
- 단점: CLI/API 사용이 어렵고 GUI 위주
- 단점: 서버 사이드 통합에 부적합 (JVM 프로세스 관리 필요)

### 옵션 5: bupaR (R)

- R 기반 Process Mining 라이브러리
- 통계 분석에 강점
- 단점: R 기반으로 Python 스택과 이질적
- 단점: 프로덕션 서버 환경에서 R 런타임 관리 부담
- 단점: pm4py 대비 기능 범위가 좁음

## 선택한 결정

**옵션 1: pm4py** 를 선택한다.

## 근거

### 1. Python 네이티브 통합

FastAPI + Python 3.11 스택에서 `import pm4py`로 즉시 사용 가능하다. 별도 프로세스, JVM, R 런타임 없이 동일 서비스 내에서 실행된다. 이는 배포 복잡도를 최소화하고, 타입 안전성(Pydantic 모델 연동)을 보장한다.

```python
# pm4py integration example
import pm4py

log = pm4py.read_xes("event_log.xes")
net, im, fm = pm4py.discover_petri_net_inductive(log)
bpmn = pm4py.discover_bpmn_inductive(log)
fitness = pm4py.fitness_token_based_replay(log, net, im, fm)
```

### 2. 3대 핵심 알고리즘 내장

Alpha Miner(기본), Heuristic Miner(노이즈 내성), Inductive Miner(사운드 보장) 세 가지 프로세스 발견 알고리즘을 모두 내장하고 있어, 이벤트 로그 품질에 따라 적절한 알고리즘을 선택할 수 있다.

### 3. Conformance Checking 내장

Token-based replay 알고리즘이 내장되어, EventStorming에서 설계한 모델(Petri Net으로 변환)과 실제 이벤트 로그 간의 적합성을 fitness/precision/generalization/simplicity 4가지 메트릭으로 정량화할 수 있다.

### 4. BPMN 자동 생성

`pm4py.discover_bpmn_inductive()`로 이벤트 로그에서 직접 BPMN 모델을 생성할 수 있다. 이를 Canvas에서 시각화하여 비즈니스 사용자에게 프로세스 맵을 제공한다.

### 5. 학술 + 산업 검증

RWTH Aachen University와 Fraunhofer FIT에서 개발되어 학술적으로 검증되었으며, 산업 환경에서도 널리 사용되고 있다. IEEE Task Force on Process Mining의 참조 구현이다.

### 6. 비용 효율

오픈소스(GPL-3.0)로 라이선스 비용이 없다. Celonis의 연간 수천만원 라이선스 대비 비용 효율이 극히 높다.

## 결과

### 긍정적 영향

- Process Mining 기능 개발 기간 3-4주 (커스텀 구현 대비 3-5개월 절감)
- Python 네이티브로 배포/운영 복잡도 최소
- 학술적으로 검증된 알고리즘으로 결과 신뢰도 확보
- BPMN 자동 생성으로 Canvas 통합 용이
- 향후 pm4py 업데이트로 신규 알고리즘 자동 확보

### 부정적 영향

- GPL-3.0 라이선스: Synapse 서비스 자체 코드의 라이선스 호환성 검토 필요
- 대규모 로그(100만+ 이벤트) 처리 시 메모리/성능 한계 가능
- pm4py의 API가 변경될 수 있음 (메이저 버전 업 시)
- GUI가 없으므로 시각화는 Canvas에서 별도 구현 필요

### 완화 방안

- GPL-3.0: Synapse는 SaaS로 제공되므로 GPL 배포 의무가 제한적. 필요시 법률 검토
- 대규모 로그: 100만 이벤트 초과 시 case 단위 샘플링, 시간 범위 분할 적용
- API 변경: pm4py 버전을 pyproject.toml에 고정, 메이저 업데이트 시 호환성 테스트
- 시각화: Canvas에서 BPMN XML 렌더링 + D3.js 기반 프로세스 맵

## 비용 상세 추정

| 항목 | pm4py | Celonis | 커스텀 |
|------|-------|---------|-------|
| 라이선스 | 무료 | ~$50K/년 | 무료 |
| 개발 기간 | 3-4주 | 2-3주 | 3-6개월 |
| 유지보수 | 낮음 (라이브러리 업데이트) | 낮음 (SaaS) | 높음 (자체 관리) |
| 인프라 | 기존 FastAPI 서버 | Celonis Cloud | 기존 서버 |
| 총 TCO (1년) | ~$0 | ~$50K+ | ~$100K+ (인건비) |

## 재검토 조건

- pm4py가 100만 이벤트에서 메모리 10GB 이상을 소비할 때
- Celonis가 Python SDK를 강화하고 self-hosted 옵션을 제공할 때
- 실시간 스트리밍 Process Mining 요구가 발생할 때 (pm4py는 배치 처리 중심)
- GPL-3.0 라이선스가 Axiom 배포 모델과 충돌할 때
- pm4py 프로젝트가 유지보수 중단될 때
- 5개 이상의 신규 알고리즘이 필요하여 ProM의 플러그인 생태계가 필수적일 때
