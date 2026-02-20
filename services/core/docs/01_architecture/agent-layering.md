# 2-Tier Autonomous Agent Layering Model

## 1. 목적
- Axiom의 자율 에이전트 구조를 "로컬 에이전트 집합"과 "글로벌 오케스트레이터(거버넌스 에이전트)"의 2계층으로 명확히 분리한다.
- 각 계층 간 호출 경계(Boundary)와 책임(Responsibility)을 고정하여, 에이전트 폭주 및 통제 불능 상태를 방지한다.

## 2. 계층 정의 및 책임

### 2.1 Layer 1: 로컬 에이전트 (Execution Layer)
- **책임**: 단일 마이크로서비스(또는 특정 Bounded Context) 내부의 도메인 로직 및 데이터 처리를 담당한다. (예: `synapse-ontology-worker`, `vision-whatif-solver`, `core-auth-agent`)
- **권한**: 
  - 자신에게 할당된 컨텍스트 내의 데이터 조회 및 조작만 허용된다.
  - 타 서비스의 에이전트는 직접 호출할 수 없다. 필수 상호작용은 도메인 이벤트(Event Bus)를 활용(Choreography)해야 한다.
- **Fail-safe**: 에러율 임계치 도달 또는 무한 루프 감지 시 로컬 에이전트 자체적으로 `Suspended` 상태로 전환된다.

### 2.2 Layer 2: 글로벌 오케스트레이터 (Governance & Orchestration Layer)
- **루트 컴포넌트**: `core-global-orchestrator`
- **책임**: 여러 서비스에 걸친 대규모 트랜잭션의 상태(Saga Pattern)를 관리하고, 로컬 에이전트들을 조율(Orchestrate)한다.
- **거버넌스 권한**:
  - 로컬 에이전트 활동에 대한 중단(Kill Switch), 재시작(Restart), 보상 트랜잭션(Compensation) 지시 권한을 독점한다.
  - 보안/정책 검사(Policy Check)를 우회하려는 로컬 에이전트 작업은 거부된다.
- **Fail-safe**: 거버넌스 에이전트에 장애가 발생하면 전체 시스템은 "수동 HITL 오버라이드" 모드로 강제 전환되며 새로운 오케스트레이션 세션 생성이 차단된다.

## 3. 호출 경계 원칙
- **Top-Down**: 글로벌 오케스트레이터는 어떤 로컬 에이전트든 API/Command 메시지를 통해 명시적으로 호출(Invoke)할 수 있다.
- **Bottom-Up 제한**: 로컬 에이전트는 글로벌 오케스트레이터의 동기식 원격 프로시저(RPC)를 임의로 호출할 수 없다. 필요한 경우 "Orchestration 필요" 이벤트를 발행하여 글로벌이 처리하도록 위임해야 한다.

## 4. 통과 기준 (Pass Criteria)
- 로컬 에이전트와 글로벌 거버넌스 간 호출 경계(Boundary) 위반이 통합 테스트 시 0건이어야 한다.
- 장애 투입 훈련(Chaos Engineering) 시, 글로벌 에이전트 Fail-safe 전환 시나리오가 성공적으로 재현되어야 한다.
