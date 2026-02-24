# ADR: Event Sourcing 평가 및 Go/No-Go 판단

> **Decision ID**: ADR-ES-001
> **Status**: DECIDED (No-Go)
> **Date**: 2026-02-24
> **Phase**: DDD-P3-02

---

## 1. 배경 (Context)

Axiom Core의 WorkItem Aggregate는 복잡한 상태 머신(TODO → IN_PROGRESS → SUBMITTED → DONE/REWORK/CANCELLED)을 운영하며,
상태 변경 이력이 BPM 감사(Audit) 및 디버깅에 중요하다.

Event Sourcing을 PoC 수준에서 평가하여, WorkItem에 대한 풀 스케일 도입 여부를 결정한다.

## 2. 평가 기준 및 결과

### 2.1 감사 추적 필요성

| 항목 | 평가 | 비고 |
|------|:----:|------|
| 법적/컴플라이언스 요구사항 여부 | **아니오** | 현재 법적 요구사항 없음 |
| 비즈니스 감사 필요성 | 중간 | "있으면 좋겠다" 수준 |
| 결론 | **No-Go 요인** | 감사 로그 테이블로 충분 |

### 2.2 시간 여행 쿼리

| 항목 | 평가 | 비고 |
|------|:----:|------|
| "특정 시점 상태" 쿼리 필요 | **낮음** | 현재 요구사항 없음 |
| 이벤트 리플레이 활용도 | 낮음 | 상태 히스토리 조회만 필요 |
| 결론 | **No-Go 요인** | updated_at + audit_log로 대체 가능 |

### 2.3 복잡성 비용

| 항목 | 평가 | 비고 |
|------|:----:|------|
| Event Store 인프라 운영 | **높음** | 별도 테이블, 리플레이 로직, 스냅샷 |
| Projection 구현 비용 | 높음 | 읽기 모델 동기화 필요 |
| 기존 코드 리팩터링 비용 | 높음 | WorkItemRepository, 모든 서비스 레이어 |
| 결론 | **Go 차단 요인** | ROI 불충분 |

### 2.4 팀 역량

| 항목 | 평가 | 비고 |
|------|:----:|------|
| Event Sourcing 운영 경험 | **없음** | 팀 학습 비용 3개월+ |
| CQRS 경험 | 중간 | Vision 서비스에 간이 CQRS 적용 중 |
| 결론 | **No-Go 요인** | 학습 곡선 대비 가치 불충분 |

### 2.5 PoC 벤치마크 결과

| 지표 | 측정값 | Go 기준 | 결과 |
|------|:------:|:------:|:----:|
| 이벤트 리플레이 (100 이벤트) | ~15ms | < 50ms | **Pass** |
| 이벤트 리플레이 (1000 이벤트) | ~120ms | < 200ms | **Pass** |
| 동시성 제어 정확성 | 100% | 100% | **Pass** |

> 성능은 합격이나, 비즈니스 가치와 복잡성 비용에서 No-Go.

## 3. 판단 (Decision)

### **No-Go: 현재 State-Based 모델 유지**

### 이유:
1. 감사 추적이 법적 요구사항이 아닌 "있으면 좋겠다" 수준
2. Event Store + Projection 인프라 운영 비용이 현재 비즈니스 가치 대비 과도
3. 팀의 Event Sourcing 운영 경험 부재 — 3개월+ 학습 비용
4. 기존 Outbox + Domain Events 패턴으로 이벤트 기반 통합이 이미 충분

## 4. 대안 (Alternative — 채택)

### 감사 로그 보강

현재 State-Based 모델을 유지하면서, 감사 추적이 필요한 경우:

1. **Outbox 이벤트 활용**: 기존 `EventOutbox` 테이블에 모든 상태 변경이 기록됨
2. **WorkItem.version**: 낙관적 동시성 제어로 변경 순서 보장
3. **Domain Events**: `WorkItemCreated`, `WorkItemStarted`, `WorkItemCompleted` 등
   이미 도메인 이벤트가 발행되므로, Vision의 CQRS Read Model에 이력이 저장됨

### PoC 코드 보존

`services/core/app/modules/process/infrastructure/event_store.py`에
WorkItemEventStore PoC 코드를 보존한다. 향후 요구사항 변경 시 참조 가능:

- `WorkItemEventStore.append()` — 이벤트 저장 (낙관적 동시성)
- `WorkItemEventStore.load()` — 이벤트 리플레이로 Aggregate 복원
- `WorkItemEventStore.get_events()` — 이벤트 히스토리 조회

## 5. 재평가 조건 (Re-evaluation Triggers)

다음 조건 중 하나라도 충족되면 Event Sourcing을 재평가한다:

1. 법적/규제 요구사항으로 완전한 감사 추적이 필수가 되는 경우
2. "특정 시점의 프로세스 상태 조회" 기능이 핵심 요구사항으로 확정되는 경우
3. 팀이 Event Sourcing 운영 경험을 3개월 이상 축적한 경우
4. WorkItem 상태 변경이 100회/초 이상으로 증가하여 상태 충돌이 빈번해지는 경우

## 6. 참조

- Phase 3 스펙: `docs/03_implementation/program/18_ddd-phase3-advanced-patterns.md` §4
- WorkItem Aggregate: `services/core/app/modules/process/domain/aggregates/work_item.py`
- Event Store PoC: `services/core/app/modules/process/infrastructure/event_store.py`
- Domain Events: `services/core/app/modules/process/domain/events.py`
