# Early Warning Action Runbook (SLA 표준)

이 문서는 모듈 전반(특히 Core Watch, Oracle, Vision 등)에서 발생하는 비즈니스 또는 시스템 이상 징후(Anomaly)에 대하여, 감지부터 해결까지 이어지는 **장애 알림/조치 폐루프(Closed-loop) SLA 표준**을 정의합니다. 

단순 'Event-Driven' 체계를 넘어, **"누가, 언제까지, 무엇을, 어떻게 해결해야 하는가?"**에 대한 명확한 규칙을 부여합니다.

## 1. 이상 징후 등급(Severity Level) 별 SLA

Watch Controller가 감지한 이벤트는 반드시 다음 3단계 중 하나로 분류되어야 하며, 각 등급은 고유의 SLA를 지닙니다.

| 등급 | 정의 | 감지 조건 예시 | RCA 발행 기한 | 부서 통보 기한 | 조치 완료 기한 (SLA) |
|---|---|---|---|---|---|
| **CRITICAL (P1)** | 비즈니스/시스템 정지, 대규모 재무 손실 예상 | - 주문 결제 실패 10% 이상 증가<br>- DB/API 연결 전면 다운<br>- 핵심 컴플라이언스(보안) 위반 | **10분 내** (자동) | **15분 내** | **2시간 내** |
| **WARNING (P2)** | 지표 저하, 부분적 장애, 사용자 경험 저하 | - KPI 목표 20% 이탈<br>- 리드 타임/응답 시간 2배 지연<br>- 큐(DLQ) 누적 증가 | **1시간 내** (반자동) | **2시간 내** | **24시간 내** |
| **INFO (P3)** | 정상 범주 내 이상, 계획된 변동, 모델 학습 제안 | - 평소와 다른 검색 쿼리 급증<br>- 새로운 도메인 용어 발견<br>- 정기 모의 시뮬레이션 결과 | - | - | Review 대상 (Daily/Weekly) |

## 2. 런북 상태 전이도 (폐루프 워크플로우)

모든 P1, P2 경보는 상태(Status) 추적을 갖는 **Ticket(Incident)**으로 취급되며, 시스템은 다음의 상태 전이를 보장(Watch)해야 합니다.

```
[DETECTED] ──(Auto)──> [RCA_GENERATED] ──(Auto)──> [NOTIFIED] ──(Manual/Agent)──> [IN_PROGRESS] ──(Manual/Agent)──> [RESOLVED]
```

1. **DETECTED**: SimpleCEP 엔진 또는 Vision Engine에서 조건 임계치 도달 즉시 생성.
2. **RCA_GENERATED**: Root Cause Engine(Vision)이 Neo4j 그래프 인과 추론을 통해 3대 근본 원인을 도출하고 리포트 생성 완료.
3. **NOTIFIED**: Core Agent가 해당 조직/부서의 채널(Slack, Email 등)에 RCA 리포트와 함께 조치 촉구 메시지 발송 완료.
4. **IN_PROGRESS**: 조직 담당자 확인 완료(ACK) 또는 조치 에이전트(Autonomous) 가동 중.
5. **RESOLVED**: 조치 완료. 원상 복귀 여부(정상 임계치 회복)를 Watch 컨테이너가 5분 이내 재검증해야 Ticket Clsoed.

## 3. 자동화 에이전트 대응 (Auto-Remediation)

일부 장애 패턴에 대하여 Global Orchestrator는 수동 조치 전 1차 자동 복구(Auto-Remediation) 런북을 실행합니다.

| 분류 | 감지 케이스 | 자동 런북 절차 (Execution Agent) |
|---|---|---|
| 컴플라이언스 | 결제 룰 우회 의심 이벤트 | 1. 해당 유저 계정 일시 정지 지시 (Core BPM) <br> 2. 위험 사유 RCA 첨부하여 Risk Tim 통보 |
| 인프라 리소스 | Worker 큐(Redis) 임계치 90% 돌파 | 1. K8s HPA 스케일아웃 임시 한도 상향 API 호출 <br> 2. 비긴급 워크아이템 수집 일시 정지(Circuit Breaker) |
| 데이터 정합성 | Data Fabric(MindsDB) 통신 오류 | 1. Standby 연결 문자열로 Connection Pool 재설정 <br> 2. 실패한 쿼리 DLQ 저장 후 연결 회복 시 자동 Replay |

## 4. 모니터링/관측성 대시보드 필수 요구사항

Early Warning 운영 대시보드는 반드시 다음 플라이휠 지표를 화면 최상단에 표출해야 합니다.
- **MTTD (Mean Time To Detect)**: 발생부터 감지까지 (Target: < 2m)
- **MTTI (Mean Time To Identify)**: 감지부터 RCA 생성까지 (Target: < 5m)
- **MTTR (Mean Time To Resolve)**: 감지부터 완료까지 (Target: P1 < 2h, P2 < 24h)
- 미준수 횟수: (월간 목표 미달 슬립률)
