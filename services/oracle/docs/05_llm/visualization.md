# 시각화 추천 알고리즘

## 이 문서가 답하는 질문

- 시각화 추천은 어떤 규칙으로 차트 유형을 선택하는가?
- 어떤 차트 유형을 지원하는가?
- 컬럼 타입 분석은 어떻게 동작하는가?

<!-- affects: 02_api, 04_frontend -->

---

## 1. 모듈 개요

`viz.py`(297줄)는 SQL 실행 결과의 컬럼 타입과 데이터 패턴을 분석하여 최적의 차트 유형을 추천한다.

---

## 2. 지원 차트 유형

| 유형 | 코드 | 용도 |
|------|------|------|
| 막대 차트 | `bar` | 카테고리별 비교 |
| 가로 막대 | `bar_horizontal` | 카테고리가 많을 때 |
| 선 차트 | `line` | 시계열 추이 |
| 파이 차트 | `pie` | 구성 비율 |
| 산점도 | `scatter` | 두 변수 간 관계 |
| KPI 카드 | `kpi_card` | 단일 숫자 강조 |
| 테이블 | `table` | 다중 컬럼 목록 |
| 영역 차트 | `area` | 누적 시계열 |

---

## 3. 추천 규칙

### 3.1 컬럼 타입 분류

```python
def classify_columns(columns: list[ColumnMeta], data: list[list]) -> ColumnProfile:
    """
    컬럼을 의미적 타입으로 분류.

    분류 결과:
    - temporal: 날짜/시간 컬럼 (date, timestamp, year/month 패턴)
    - categorical: 범주형 (VARCHAR with < 20 distinct values)
    - numeric: 수치형 (integer, decimal, float)
    - identifier: 식별자 (PK, ID, code)
    - text: 장문 텍스트
    """
```

### 3.2 규칙 기반 추천

```python
def recommend_chart(profile: ColumnProfile, row_count: int) -> VizRecommendation:
    """
    컬럼 프로파일과 행 수에 따른 차트 추천.

    규칙 (우선순위 순):
    """

    # Rule 1: 단일 행, 단일 숫자 → KPI 카드
    if row_count == 1 and len(profile.numeric) == 1:
        return VizRecommendation(
            chart_type="kpi_card",
            config={
                "value_column": profile.numeric[0].name,
                "label": _infer_label(profile.numeric[0])
            }
        )

    # Rule 2: 시계열 + 숫자 → 선 차트
    if profile.temporal and profile.numeric:
        return VizRecommendation(
            chart_type="line",
            config={
                "x_column": profile.temporal[0].name,
                "y_columns": [c.name for c in profile.numeric],
                "x_label": profile.temporal[0].description or "날짜"
            }
        )

    # Rule 3: 카테고리 + 숫자 (카테고리 <= 10) → 막대 차트
    if profile.categorical and profile.numeric:
        distinct_count = _count_distinct(profile.categorical[0], data)
        if distinct_count <= 10:
            return VizRecommendation(
                chart_type="bar",
                config={
                    "x_column": profile.categorical[0].name,
                    "y_column": profile.numeric[0].name
                }
            )

    # Rule 4: 카테고리 + 숫자 (카테고리 > 10) → 가로 막대
    if profile.categorical and profile.numeric:
        return VizRecommendation(
            chart_type="bar_horizontal",
            config={
                "y_column": profile.categorical[0].name,
                "x_column": profile.numeric[0].name
            }
        )

    # Rule 5: 카테고리 + 비율 숫자 (합계 = 100 또는 1.0) → 파이 차트
    if profile.categorical and profile.numeric:
        if _is_percentage(profile.numeric[0], data):
            return VizRecommendation(
                chart_type="pie",
                config={
                    "label_column": profile.categorical[0].name,
                    "value_column": profile.numeric[0].name
                }
            )

    # Rule 6: 두 숫자 컬럼 → 산점도
    if len(profile.numeric) >= 2 and not profile.temporal:
        return VizRecommendation(
            chart_type="scatter",
            config={
                "x_column": profile.numeric[0].name,
                "y_column": profile.numeric[1].name
            }
        )

    # Rule 7: 기본 → 테이블
    return VizRecommendation(
        chart_type="table",
        config={
            "columns": [c.name for c in columns]
        }
    )
```

### 3.3 규칙 판단 다이어그램

```
                        ┌──────────────────┐
                        │ 행 수 == 1 AND   │
                     Yes│ 숫자 컬럼 1개?   │
                  ┌─────┤                  │
                  │     └────────┬─────────┘
                  ▼              │ No
            ┌──────────┐        ▼
            │ KPI Card │   ┌──────────────┐
            └──────────┘   │ 시계열 컬럼   │
                        Yes│ 존재?         │
                     ┌─────┤               │
                     │     └───────┬───────┘
                     ▼             │ No
               ┌──────────┐       ▼
               │ Line     │  ┌──────────────┐
               └──────────┘  │ 카테고리 +   │
                          Yes│ 숫자 존재?    │
                        ┌────┤              │
                        │    └──────┬───────┘
                        ▼          │ No
                  ┌──────────┐     ▼
                  │ Bar /    │  ┌──────────┐
                  │ Pie      │  │ 숫자 2+ ?│
                  └──────────┘  └─────┬────┘
                                 Yes  │ No
                              ┌───────┼────┐
                              ▼            ▼
                         ┌─────────┐  ┌────────┐
                         │ Scatter │  │ Table  │
                         └─────────┘  └────────┘
```

---

## 4. 시각화 응답 구조

```python
@dataclass
class VizRecommendation:
    chart_type: str              # bar, line, pie, scatter, kpi_card, table
    config: dict                 # 차트별 설정
    alternative: str | None = None  # 대안 차트 유형
    reasoning: str | None = None    # 추천 이유
```

```json
{
    "chart_type": "bar",
    "config": {
        "x_column": "org_name",
        "y_column": "process_count",
        "x_label": "조직",
        "y_label": "건수",
        "sort": "descending"
    },
    "alternative": "pie",
    "reasoning": "카테고리(조직)별 숫자(건수) 비교에 막대 차트가 적합합니다"
}
```

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| 규칙 기반 추천 (LLM 아님) | 결정적 결과 필요, LLM 비용 절약 |
| KPI 카드 최우선 | 단일 숫자 결과가 가장 빈번 |
| 기본값 테이블 | 판단 불가 시 데이터 손실 없는 형태 |

## 관련 문서

- [02_api/text2sql-api.md](../02_api/text2sql-api.md): 시각화 응답 형식
