# CEP 이벤트 감지 엔진

## 이 문서가 답하는 질문

- CEP 엔진은 어떤 역할을 하는가?
- K-AIR의 SimpleCEP는 어떻게 동작했는가?
- Axiom에서는 왜 Core Watch로 이관하는가?
- 이관 전/후 아키텍처는 어떻게 달라지는가?

<!-- affects: 02_api, 08_operations -->
<!-- requires-update: 02_api/events-api.md -->

---

## 1. CEP 엔진 개요

### 1.1 CEP란

CEP(Complex Event Processing)는 데이터 스트림에서 특정 조건/패턴이 충족되면 이벤트를 발생시키는 기술이다.

Oracle에서의 CEP 역할:

- **이벤트 룰**: "프로세스 마일스톤 기한 3일 전" 같은 조건 등록
- **주기적 감시**: SQL을 주기적으로 실행하여 조건 충족 여부 확인
- **알림 발생**: 조건 충족 시 알림 생성 (SSE 스트림, 웹훅 등)

### 1.2 K-AIR SimpleCEP 구현

K-AIR `robo-data-text2sql-main`에는 **SimpleCEP** 엔진이 내장되어 있었다.

```
┌─────────────────────────────────────────────────────────────┐
│  K-AIR SimpleCEP (text2sql 내장)                            │
│                                                              │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐│
│  │ 이벤트   │  │ 스케줄러     │  │ 알림 시스템            ││
│  │ 룰 CRUD  │→│ (APScheduler)│→│ SSE 스트림 /           ││
│  │ /events/ │  │ 주기적 실행  │  │ events/stream/alarms   ││
│  └──────────┘  └──────────────┘  └────────────────────────┘│
│       │              │                    │                  │
│       ▼              ▼                    ▼                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  SQLite (이벤트 룰 저장) + Target DB (SQL 실행)      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**K-AIR 구현 상세**:

| 컴포넌트 | 파일 | 설명 |
|----------|------|------|
| 이벤트 룰 CRUD | `app/routers/events.py` (46KB) | 룰 생성/수정/삭제/목록 |
| SimpleCEP 엔진 | `app/core/simple_cep.py` | 이벤트 조건 평가 + SQL 실행 |
| 스케줄러 | events.py 내 APScheduler | 주기적 룰 실행 |
| SSE 알림 | `/events/stream/alarms` | Server-Sent Events 실시간 알림 |
| 감시 에이전트 | `/watch-agent/chat` | LLM 기반 감시 대화 |

### 1.3 이벤트 룰 구조

```json
{
    "rule_id": "rule_001",
    "name": "프로세스 마일스톤 기한 임박 알림",
    "description": "마일스톤 기한 3일 전 알림",
    "sql": "SELECT process_id, milestone_deadline FROM process_milestones WHERE milestone_deadline BETWEEN NOW() AND NOW() + INTERVAL '3 days'",
    "schedule": {
        "type": "interval",
        "value": "1h"
    },
    "condition": {
        "type": "row_count",
        "operator": "gt",
        "threshold": 0
    },
    "actions": [
        {
            "type": "notification",
            "channel": "sse",
            "template": "프로세스 {process_id}의 마일스톤 기한이 {milestone_deadline}에 임박했습니다."
        }
    ],
    "enabled": true
}
```

---

## 2. Axiom Core Watch 이관 계획

### 2.1 이관 근거

| 근거 | 설명 |
|------|------|
| **공통 관심사** | 이벤트 감시는 Oracle뿐 아니라 Vision, Weaver 등 다른 모듈에서도 필요 |
| **관심사 분리** | NL2SQL과 이벤트 스케줄링은 서로 다른 관심사 |
| **확장성** | 이벤트 룰이 많아지면 전용 스케줄러가 필요 |
| **운영 독립성** | 이벤트 엔진 장애가 NL2SQL에 영향을 주지 않아야 함 |

### 2.2 이관 전후 비교

```
[이관 전: K-AIR 구조]

┌─────────────────────────────┐
│  Oracle (text2sql)           │
│  ┌────────────────────────┐ │
│  │ NL2SQL Pipeline        │ │
│  ├────────────────────────┤ │
│  │ SimpleCEP Engine       │ │  ← 이벤트 엔진이 NL2SQL에 종속
│  │ - 룰 CRUD              │ │
│  │ - 스케줄러              │ │
│  │ - SSE 알림              │ │
│  └────────────────────────┘ │
└─────────────────────────────┘

        ↓ 이관 ↓

[이관 후: Axiom 구조]

┌──────────────┐    ┌──────────────────────────────────────┐
│  Oracle       │    │  Core Watch (공통 모듈)               │
│  ┌──────────┐│    │  ┌──────────────────────────────────┐│
│  │ NL2SQL   ││    │  │ Event Engine                      ││
│  │ Pipeline ││    │  │ - 룰 CRUD (REST API)              ││
│  └──────────┘│    │  │ - 스케줄러 (분산)                  ││
│              │    │  │ - 알림 (웹훅/SSE/이벤트 버스)      ││
│  Oracle은    │    │  │ - 감시 에이전트                    ││
│  NL2SQL에    │    │  └──────────────────────────────────┘│
│  집중        │    │                                       │
└──────┬───────┘    │  SQL 실행 요청                        │
       │            │  (Oracle에 위임)                      │
       │            └───────────────┬──────────────────────┘
       │                            │
       └────────────────────────────┘
        Core Watch가 Oracle에 SQL 실행 위임
```

### 2.3 이관 단계

| 단계 | 작업 | 상태 |
|------|------|------|
| 1 | Oracle 내 SimpleCEP를 그대로 이식 (호환성 유지) | 미착수 |
| 2 | Core Watch 모듈 기본 구조 설계 | 미착수 |
| 3 | 이벤트 룰 API를 Core Watch로 이동 | 미착수 |
| 4 | Oracle의 이벤트 API를 Core Watch proxy로 전환 | 미착수 |
| 5 | Oracle 내 SimpleCEP 코드 제거 | 미착수 |

### 2.4 Oracle 잔존 인터페이스

이관 후에도 Oracle에는 다음 인터페이스가 남는다:

```python
# Oracle이 Core Watch에 제공하는 인터페이스
class OracleSQLExecutor:
    """
    Core Watch가 이벤트 룰의 SQL을 Oracle에 위임 실행할 때 사용.
    SQL Guard 검증은 동일하게 적용.
    """
    async def execute_rule_sql(
        self,
        sql: str,
        datasource_id: str,
        rule_id: str
    ) -> RuleExecutionResult:
        # 1. SQL Guard 검증
        # 2. SQL 실행
        # 3. 결과 반환
        pass
```

---

## 3. 감시 에이전트

### 3.1 현재 구조 (K-AIR)

K-AIR의 `/watch-agent/chat` 엔드포인트는 LLM 기반 감시 대화 에이전트이다.

```
사용자: "매출이 10% 이상 떨어진 부서를 알려줘"
    │
    ▼
감시 에이전트:
  1. NL2SQL로 현재 매출 데이터 조회
  2. 이전 기간 매출 데이터 조회
  3. 비교 분석
  4. 조건 충족 부서 목록 반환
  5. (선택) 이벤트 룰 자동 등록 제안
```

### 3.2 Axiom 이관 후 구조

감시 에이전트는 Core Watch로 이관되며, Oracle은 SQL 실행 백엔드 역할만 수행한다.

---

## 4. 이관 기간 호환성

이관 완료 전까지 Oracle은 K-AIR의 이벤트 API를 그대로 제공한다:

| API | 이관 전 | 이관 후 |
|-----|--------|--------|
| `POST /events/rules` | Oracle 직접 처리 | Core Watch로 프록시 |
| `GET /events/rules` | Oracle 직접 처리 | Core Watch로 프록시 |
| `POST /events/scheduler/start` | Oracle 내 스케줄러 | Core Watch 스케줄러 |
| `GET /events/stream/alarms` | Oracle SSE | Core Watch SSE |
| `POST /watch-agent/chat` | Oracle 내 에이전트 | Core Watch 에이전트 |

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| SimpleCEP를 Core Watch로 이관 | 이벤트 감시는 여러 서비스가 공유해야 할 공통 관심사 |
| 이관 전 호환성 유지 | 기존 API를 깨지 않고 점진적 이관 |
| Oracle은 SQL 실행 백엔드로 잔존 | 이벤트 룰의 SQL 실행은 Oracle의 전문 영역 |

## 관련 문서

- [02_api/events-api.md](../02_api/events-api.md): 이벤트 API 스펙
- [08_operations/deployment.md](../08_operations/deployment.md): Core Watch 배포 계획
