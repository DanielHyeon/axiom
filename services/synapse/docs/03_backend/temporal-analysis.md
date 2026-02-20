# Temporal Analysis 구현 상세

## 이 문서가 답하는 질문

- 활동별 소요시간 통계는 어떻게 계산하는가?
- 활동 간 대기시간 분석은 어떻게 하는가?
- SLA 위반 탐지 알고리즘은?
- 병목 점수(Bottleneck Score)는 어떻게 산출하는가?
- 시계열 추세 분석(프로세스 속도 변화)은 어떻게 하는가?
- 케이스 소요시간 예측은 가능한가?

<!-- affects: api, data, frontend -->
<!-- requires-update: 02_api/process-mining-api.md, 06_data/neo4j-schema.md -->

---

## 1. 시간축 분석 개요

### 1.1 분석 대상

| 분석 유형 | 질문 | 결과 |
|----------|------|------|
| **Activity Duration** | "각 활동에 얼마나 걸리는가?" | 활동별 평균/중위/P95 소요시간 |
| **Waiting Time** | "활동 사이에 얼마나 기다리는가?" | 활동 쌍 간 대기시간 통계 |
| **SLA Violation** | "어떤 활동이 SLA를 초과하는가?" | 위반율, 위반 케이스 목록 |
| **Bottleneck Score** | "전체 프로세스에서 가장 느린 곳은?" | 활동별 병목 점수 (0-1) |
| **Trend Analysis** | "프로세스가 빨라지는가, 느려지는가?" | 월별 추세, 변화율 |
| **Case Duration Prediction** | "새 케이스는 얼마나 걸릴 것인가?" | 예측 소요시간 + 신뢰구간 |

---

## 2. Activity Duration 분석

### 2.1 소요시간 계산

```python
import pm4py
import pandas as pd
import numpy as np

async def analyze_activity_durations(df: pd.DataFrame) -> list[ActivityDurationStats]:
    """
    Calculate duration statistics per activity.
    Duration = time from activity start to next activity start (sojourn time).
    """
    results = []

    # Calculate sojourn time per event
    df_sorted = df.sort_values(['case:concept:name', 'time:timestamp'])
    df_sorted['next_timestamp'] = df_sorted.groupby('case:concept:name')['time:timestamp'].shift(-1)
    df_sorted['duration_seconds'] = (
        df_sorted['next_timestamp'] - df_sorted['time:timestamp']
    ).dt.total_seconds()

    # Aggregate per activity
    for activity, group in df_sorted.groupby('concept:name'):
        durations = group['duration_seconds'].dropna()

        if len(durations) == 0:
            continue

        results.append(ActivityDurationStats(
            activity=activity,
            frequency=len(group),
            avg_seconds=float(durations.mean()),
            median_seconds=float(durations.median()),
            min_seconds=float(durations.min()),
            max_seconds=float(durations.max()),
            p25_seconds=float(durations.quantile(0.25)),
            p75_seconds=float(durations.quantile(0.75)),
            p95_seconds=float(durations.quantile(0.95)),
            std_seconds=float(durations.std()),
        ))

    return sorted(results, key=lambda x: x.avg_seconds, reverse=True)
```

---

## 3. Waiting Time 분석

### 3.1 대기시간 계산

대기시간은 한 활동의 완료와 다음 활동의 시작 사이의 시간이다.

```python
async def analyze_waiting_times(df: pd.DataFrame) -> list[WaitingTimeStats]:
    """
    Calculate waiting time between consecutive activities.
    Waiting time = time between completion of activity A and start of activity B.
    """
    results = []

    df_sorted = df.sort_values(['case:concept:name', 'time:timestamp'])

    # Pair consecutive activities
    df_sorted['next_activity'] = df_sorted.groupby('case:concept:name')['concept:name'].shift(-1)
    df_sorted['next_timestamp'] = df_sorted.groupby('case:concept:name')['time:timestamp'].shift(-1)
    df_sorted['waiting_seconds'] = (
        df_sorted['next_timestamp'] - df_sorted['time:timestamp']
    ).dt.total_seconds()

    # Aggregate per activity pair
    pairs = df_sorted.dropna(subset=['next_activity']).groupby(
        ['concept:name', 'next_activity']
    )

    for (from_act, to_act), group in pairs:
        waits = group['waiting_seconds']
        results.append(WaitingTimeStats(
            from_activity=from_act,
            to_activity=to_act,
            case_count=len(group),
            avg_seconds=float(waits.mean()),
            median_seconds=float(waits.median()),
            p95_seconds=float(waits.quantile(0.95)),
        ))

    return sorted(results, key=lambda x: x.avg_seconds, reverse=True)
```

---

## 4. SLA Violation 탐지

### 4.1 SLA 소스

SLA 기준값은 다음 소스에서 가져온다:

| 소스 | 우선순위 | 설명 |
|------|---------|------|
| EventStorming 모델 | 1 (최우선) | BusinessEvent 노드의 `sla_threshold` 속성 |
| 수동 설정 | 2 | API로 직접 입력된 SLA |
| 자동 추정 | 3 (대안) | P95 기반 자동 추정 (SLA 미설정 시) |

### 4.2 SLA 위반 탐지 구현

```python
async def detect_sla_violations(
    df: pd.DataFrame,
    sla_config: dict[str, float],  # activity_name -> sla_threshold_seconds
    auto_estimate: bool = True
) -> SLAViolationReport:
    """
    Detect SLA violations per activity.
    """
    duration_stats = await analyze_activity_durations(df)
    violations = []

    for stat in duration_stats:
        # Determine SLA threshold
        sla_threshold = sla_config.get(stat.activity)

        if sla_threshold is None and auto_estimate:
            # Auto-estimate: P95 as threshold
            sla_threshold = stat.p95_seconds

        if sla_threshold is None:
            continue

        # Calculate violations
        activity_durations = get_activity_durations(df, stat.activity)
        violation_count = sum(1 for d in activity_durations if d > sla_threshold)
        violation_rate = violation_count / len(activity_durations) if activity_durations else 0

        violations.append(SLAViolation(
            activity=stat.activity,
            sla_threshold_seconds=sla_threshold,
            violation_count=violation_count,
            total_cases=len(activity_durations),
            violation_rate=violation_rate,
            avg_violation_excess_seconds=(
                float(np.mean([d - sla_threshold for d in activity_durations if d > sla_threshold]))
                if violation_count > 0 else 0
            ),
        ))

    return SLAViolationReport(
        violations=sorted(violations, key=lambda x: x.violation_rate, reverse=True),
        total_violations=sum(v.violation_count for v in violations),
        overall_compliance_rate=1.0 - (
            sum(v.violation_count for v in violations) /
            sum(v.total_cases for v in violations)
        ) if violations else 1.0
    )
```

### 4.3 Neo4j 시간축 속성 업데이트

SLA 분석 결과를 EventStorming 노드의 시간축 속성에 반영한다.

```python
async def update_temporal_properties(
    neo4j: Neo4jClient,
    case_id: str,
    duration_stats: list[ActivityDurationStats],
    sla_report: SLAViolationReport
):
    """
    Update BusinessEvent nodes with actual temporal properties from event log.
    """
    async with neo4j.session() as session:
        for stat in duration_stats:
            sla_violation = next(
                (v for v in sla_report.violations if v.activity == stat.activity),
                None
            )

            await session.run("""
                MATCH (e:BusinessEvent:Process {case_id: $case_id, name: $name})
                SET e.actual_avg_duration = $avg_duration,
                    e.violation_rate = $violation_rate,
                    e.updated_at = datetime()
                """,
                case_id=case_id,
                name=stat.activity,
                avg_duration=stat.avg_seconds,
                violation_rate=sla_violation.violation_rate if sla_violation else 0.0,
            )
```

---

## 5. Bottleneck Score 산출

### 5.1 병목 점수 알고리즘

병목 점수는 여러 요인을 결합한 복합 지표이다.

```python
def calculate_bottleneck_score(
    avg_duration: float,
    max_duration_in_process: float,
    sla_violation_rate: float,
    waiting_time_ratio: float,  # waiting_time / total_duration
    frequency: int,
    total_cases: int
) -> float:
    """
    Bottleneck Score (0.0 - 1.0)

    Components:
    - Duration ratio (40%): How long compared to longest activity
    - SLA violation (30%): How often SLA is violated
    - Waiting time (20%): How much time is waiting vs processing
    - Frequency impact (10%): How often this activity occurs

    Higher = more bottleneck
    """
    # Duration component (0-1): relative to longest activity
    duration_score = avg_duration / max_duration_in_process if max_duration_in_process > 0 else 0

    # SLA violation component (0-1): direct violation rate
    sla_score = min(sla_violation_rate, 1.0)

    # Waiting time component (0-1): high waiting = bottleneck upstream
    waiting_score = min(waiting_time_ratio, 1.0)

    # Frequency component (0-1): high frequency = more impact
    frequency_score = frequency / total_cases if total_cases > 0 else 0

    # Weighted combination
    bottleneck_score = (
        0.40 * duration_score +
        0.30 * sla_score +
        0.20 * waiting_score +
        0.10 * frequency_score
    )

    return round(min(bottleneck_score, 1.0), 3)
```

### 5.2 병목 점수 해석

| 점수 범위 | 해석 | 권장 행동 |
|----------|------|----------|
| 0.0 - 0.3 | 원활 | 모니터링 유지 |
| 0.3 - 0.6 | 주의 | 추세 관찰, 개선 검토 |
| 0.6 - 0.8 | 병목 | 즉시 개선 필요 |
| 0.8 - 1.0 | 심각한 병목 | 긴급 대응 필요 |

---

## 6. Trend Analysis (추세 분석)

### 6.1 시계열 추세 계산

```python
from scipy import stats

async def analyze_trends(
    df: pd.DataFrame,
    period: str = "month"  # month, week, day
) -> list[TrendAnalysis]:
    """
    Analyze temporal trends per activity.
    Detects if process is getting slower or faster over time.
    """
    results = []

    df_sorted = df.sort_values(['case:concept:name', 'time:timestamp'])
    df_sorted['duration_seconds'] = calculate_durations(df_sorted)

    # Group by period
    if period == "month":
        df_sorted['period'] = df_sorted['time:timestamp'].dt.to_period('M')
    elif period == "week":
        df_sorted['period'] = df_sorted['time:timestamp'].dt.to_period('W')

    for activity, activity_group in df_sorted.groupby('concept:name'):
        period_stats = activity_group.groupby('period')['duration_seconds'].agg(['mean', 'count'])

        if len(period_stats) < 3:
            continue  # Need at least 3 periods for trend

        # Linear regression for trend detection
        x = np.arange(len(period_stats))
        y = period_stats['mean'].values
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

        # Determine trend direction
        if p_value < 0.05:  # Statistically significant
            if slope > 0:
                direction = "worsening"
                change_rate = slope / y[0] if y[0] > 0 else 0  # relative change per period
            else:
                direction = "improving"
                change_rate = abs(slope) / y[0] if y[0] > 0 else 0
        else:
            direction = "stable"
            change_rate = 0

        results.append(TrendAnalysis(
            activity=activity,
            direction=direction,
            change_rate_per_period=round(change_rate, 4),
            p_value=round(p_value, 4),
            period_count=len(period_stats),
            first_period_avg=float(y[0]),
            last_period_avg=float(y[-1]),
            description=generate_trend_description(activity, direction, change_rate, period)
        ))

    return results


def generate_trend_description(
    activity: str, direction: str, change_rate: float, period: str
) -> str:
    period_kr = {"month": "월", "week": "주", "day": "일"}[period]

    if direction == "stable":
        return f"'{activity}' 소요시간이 안정적"
    elif direction == "worsening":
        return f"'{activity}' 소요시간이 {period_kr} {change_rate*100:.1f}%씩 증가 추세"
    else:
        return f"'{activity}' 소요시간이 {period_kr} {change_rate*100:.1f}%씩 감소 추세"
```

---

## 7. Case Duration Prediction

### 7.1 단순 예측 모델

진행 중인 케이스의 남은 소요시간을 예측한다.

```python
async def predict_case_duration(
    df: pd.DataFrame,
    current_activity: str,
    elapsed_seconds: float
) -> DurationPrediction:
    """
    Predict remaining duration for an in-progress case.
    Based on historical data for cases that passed through the same activity.
    """
    # Filter cases that went through current activity
    cases_with_activity = df[df['concept:name'] == current_activity]['case:concept:name'].unique()

    # Calculate total duration for completed cases
    case_durations = []
    for case_id in cases_with_activity:
        case_events = df[df['case:concept:name'] == case_id].sort_values('time:timestamp')
        total_duration = (
            case_events['time:timestamp'].max() - case_events['time:timestamp'].min()
        ).total_seconds()
        case_durations.append(total_duration)

    if not case_durations:
        return None

    avg_total = np.mean(case_durations)
    std_total = np.std(case_durations)

    predicted_remaining = max(0, avg_total - elapsed_seconds)

    return DurationPrediction(
        predicted_remaining_seconds=predicted_remaining,
        predicted_total_seconds=avg_total,
        confidence_interval_low=max(0, avg_total - 1.96 * std_total - elapsed_seconds),
        confidence_interval_high=max(0, avg_total + 1.96 * std_total - elapsed_seconds),
        based_on_cases=len(case_durations),
    )
```

---

## 금지 규칙

- SLA 기준 없이 위반율을 보고하지 않는다 (auto_estimate 사용 시 명시)
- 3개 미만의 기간 데이터로 추세를 판단하지 않는다
- p_value >= 0.05인 추세를 "확정적"으로 보고하지 않는다

## 필수 규칙

- 시간축 분석 결과를 Neo4j BusinessEvent 노드에 반영한다
- 병목 점수 산출에 사용된 가중치와 공식을 기록한다
- 추세 분석에 통계적 유의성(p_value)을 포함한다

---

## 8. Temporal 통계 → Measure 계층 바인딩

시간축 분석에서 산출된 통계값은 4계층 온톨로지의 Measure 계층 노드로 자동 변환된다. 이를 통해 프로세스 성능 데이터가 온톨로지 그래프에 통합되어 KPI까지의 인과 추적이 가능해진다.

### 8.1 변환 규칙

| Temporal 통계 | Measure 노드 유형 | 속성 매핑 | 설명 |
|-------------|-----------------|----------|------|
| 활동별 `avg_duration` | `:CycleTime:Measure` (type="CycleTime") | duration=avg_seconds, unit="seconds", process_id=활동 ID | 각 활동의 평균 소요시간 |
| SLA `violation_rate` | `:Measure` (type="SLACompliance") | rate=1.0-violation_rate, threshold=sla_threshold | SLA 준수율 (1 - 위반율) |
| `bottleneck_score` | `:Measure` (type="BottleneckScore") | score=bottleneck_score, rank=bottleneck_rank | 활동별 병목 점수 |

### 8.2 KPI 연결

생성된 Measure 노드는 상위 프로세스 KPI에 `CONTRIBUTES_TO` 관계로 연결된다.

```
(:BusinessEvent {name: "출하 지시"})
    │ PRODUCES
    ▼
(:CycleTime:Measure {duration: 7200, type: "CycleTime"})
(:Measure {rate: 0.746, type: "SLACompliance"})
(:Measure {score: 0.89, type: "BottleneckScore"})
    │ CONTRIBUTES_TO
    ▼
(:ProcessEfficiency:KPI {name: "물류 프로세스 효율성"})
```

Measure 노드는 이벤트 로그 재분석 시 자동으로 갱신되며, `source="calculated"`, `confidence=1.0` 속성을 갖는다.

---

## 근거 문서

- `01_architecture/process-mining-engine.md` (엔진 아키텍처)
- `02_api/process-mining-api.md` (API 명세 - /bottlenecks)
- `01_architecture/ontology-4layer.md` (4계층 온톨로지 - Measure/KPI 계층)
- `06_data/neo4j-schema.md` (BusinessEvent 시간축 속성)
- `06_data/event-log-schema.md` (이벤트 로그 스키마)
