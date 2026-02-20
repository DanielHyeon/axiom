# LLM 기반 인과 설명 서술문 생성

> **최종 수정일**: 2026-02-19
> **상태**: Draft
> **Phase**: 4
> **근거**: 01_architecture/root-cause-engine.md

---

## 이 문서가 답하는 질문

- LLM이 인과 분석 결과를 어떻게 서술문으로 변환하는가?
- 프롬프트 구조와 정책은 어떻게 되는가?
- Hallucination을 어떻게 방지하는가?
- 분석 보고서 자동 작성과 어떻게 연동되는가?

---

## 1. LLM 역할 정의

### 1.1 See-Why에서 LLM이 하는 것

- 인과 분석 결과(SHAP 값, 근본원인, 반사실)를 **한국어 서술문**으로 변환
- 분석 보고서에 사용 가능한 전문적 문체로 작성
- 수치 근거를 포함한 객관적 설명 생성

### 1.2 LLM이 하지 않는 것

- 인과 관계 자체를 판단하지 않음 (DoWhy가 수행)
- 근본원인을 선택하지 않음 (SHAP 값이 결정)
- 확률을 계산하지 않음 (통계 모델이 계산)

> LLM은 **번역기**이다. 통계 결과를 사람이 읽을 수 있는 한국어로 번역한다.

---

## 2. 프롬프트 구조 (5-Block 패턴)

```python
CAUSAL_EXPLANATION_PROMPT = """
{role_block}

{glossary_block}

{data_block}

{output_format_block}

{guardrails_block}
"""
```

### 2.1 Role Block

```
당신은 기업 비즈니스 프로세스 분석 보조 AI입니다.
인과 분석 결과를 바탕으로 비즈니스 실패 원인 설명문을 작성합니다.
분석 보고서에 포함될 수 있는 수준의 전문적이고 객관적인 문체를 사용하세요.
```

### 2.2 Glossary Block

```yaml
# Domain glossary (YAML format included in prompt)
glossary:
  부채비율: "총부채 / 자기자본 x 100. 100% 이상이면 부채가 자본을 초과."
  EBITDA: "이자, 세금, 감가상각 전 영업이익. 기업의 영업 현금 창출력 지표."
  DSCR: "Debt Service Coverage Ratio. 원리금 상환 능력. 1.0 미만이면 상환 능력 부족."
  사업실패: "대상 조직이 비즈니스 목표를 달성하지 못하고 지속가능성이 위협받는 상태."
  자산 가치 보장 원칙: "자산의 가치가 적정 수준으로 유지되어야 한다는 원칙."
  SHAP_value: "각 요인이 최종 결과(실패)에 미친 기여도. 양수이면 실패 확률 증가, 음수이면 감소."
```

### 2.3 Data Block (LLM에 전달되는 분석 결과)

```python
def build_data_block(
    case_info: dict,
    root_causes: list[RootCause],
    causal_chain: list[CausalEvent],
    counterfactuals: list[CounterfactualResult],
    shap_result: SHAPResult
) -> str:
    """
    Build structured data block for LLM prompt.
    Only computed facts - no opinions or interpretations.
    """
    return f"""
## 분석 대상 사건
- 회사명: {case_info['company_name']}
- 사건번호: {case_info['case_number']}
- 사건유형: {case_info['case_type']}
- 분석 기준일: {case_info['declaration_date']}
- 업종: {case_info['industry']}
- 총 금액: {format_krw(case_info['total_amount'])}
- 총 자산: {format_krw(case_info['total_assets'])}

## 근본원인 (SHAP 기여도 순)
{format_root_causes(root_causes)}

## 인과 체인 (시간순)
{format_causal_chain(causal_chain)}

## 반사실 분석 결과
{format_counterfactuals(counterfactuals)}

## SHAP 기여도 요약
- 기본 실패 확률 (평균): {shap_result.base_value:.1%}
- 이 사건 실패 확률: {shap_result.predicted_value:.1%}
- 주요 증가 요인: {format_positive_contributions(shap_result)}
- 주요 감소 요인: {format_negative_contributions(shap_result)}
"""
```

### 2.4 Output Format Block

```
## 작성 규칙
1. 시간 순서대로 인과 관계를 서술하세요.
2. 각 원인의 SHAP 기여도를 수치(%)로 명시하세요.
3. 반사실 분석 결과를 "만약 ~했다면" 형태로 제시하세요.
4. 300~500자 분량으로 작성하세요.
5. 단락 구분: (1) 핵심 원인 요약, (2) 인과 경과, (3) 반사실 시사점.

## 출력 형식 (JSON)
{
  "summary": "1~2문장 핵심 원인 요약",
  "detailed_explanation": "3단락 서술문",
  "key_figures": [
    {"label": "지표명", "value": "값", "significance": "의미"}
  ],
  "recommendations": ["향후 유사 사건 예방 시사점"]
}
```

### 2.5 Guardrails Block

```
## 금지 사항
- 제공된 데이터에 없는 사실을 창작하지 마세요.
- "~일 것이다", "~로 추정된다" 등 불확실한 표현은 명시적으로 표시하세요.
- 인과 관계가 아닌 상관관계를 인과로 서술하지 마세요.
- SHAP 기여도가 아닌 다른 수치를 기여도로 제시하지 마세요.
- 법적 판단이나 규제 관련 판단을 내리지 마세요.

## 필수 포함 사항
- 분석 대상 사건번호와 회사명
- 각 근본원인의 SHAP 기여도 (%)
- 최소 1개의 반사실 시나리오 결과
- 분석의 한계점 또는 주의사항 (confidence < 0.80인 경우)

## 분석 한계 고지 (confidence에 따라)
- confidence >= 0.80: "본 분석은 통계적으로 유의한 인과 관계에 기반합니다."
- 0.70 <= confidence < 0.80: "본 분석의 일부 인과 연결은 참고용이며, 전문가 검토가 필요합니다."
- confidence < 0.70: 생성하지 않음 (데이터 부족으로 분석 불가)
```

---

## 3. Hallucination 방지 전략

| 전략 | 구현 방법 |
|------|----------|
| **Ground Truth Only** | LLM에 전달하는 데이터는 DoWhy/SHAP 계산 결과만 (원시 데이터 아님) |
| **수치 검증** | 생성된 텍스트에서 수치 추출 → 원본 데이터와 비교 |
| **출처 명시** | 모든 수치에 "SHAP 분석 결과" 등 출처 표기 요구 |
| **금지 키워드** | "확실히", "반드시", "명백히" 등 과도한 확신 표현 차단 |
| **Temperature 0** | 재현성을 위해 temperature=0 사용 |
| **Post-processing** | JSON 출력 파싱 후 수치 일관성 검증 |

### 3.1 수치 검증 코드

```python
def verify_explanation_numbers(
    explanation: dict,
    root_causes: list[RootCause],
    shap_result: SHAPResult
) -> list[str]:
    """
    Verify that numbers in LLM output match the source data.
    Returns list of discrepancies.
    """
    discrepancies = []

    # Extract percentages from text
    import re
    numbers_in_text = re.findall(r'(\d+\.?\d*)%', explanation['detailed_explanation'])

    # Check key figures
    for figure in explanation.get('key_figures', []):
        if 'SHAP' in figure.get('label', '') or '기여도' in figure.get('label', ''):
            expected = next(
                (rc.contribution_pct for rc in root_causes
                 if rc.variable_label in figure['label']),
                None
            )
            if expected and abs(float(figure['value'].rstrip('%')) - expected) > 1.0:
                discrepancies.append(
                    f"Key figure mismatch: {figure['label']} = {figure['value']}, "
                    f"expected {expected}%"
                )

    return discrepancies
```

---

## 4. 분석 보고서 연동

### 4.1 연동 흐름

```
See-Why 분석 완료
    │
    ▼
LLM 설명문 생성 (이 워크플로우)
    │
    ├─ summary: 분석 보고서 "원인 요약" 섹션에 삽입
    ├─ detailed_explanation: 분석 보고서 "상세 분석" 섹션에 삽입
    ├─ key_figures: 분석 보고서 "주요 지표" 표에 삽입
    └─ recommendations: 분석 보고서 "시사점" 섹션에 삽입
    │
    ▼
Axiom Core 문서 생성 워커 (worker-generate)
    → DOCX 템플릿에 삽입
    → PDF 변환
```

### 4.2 분석 보고서 템플릿 슬롯

```
[분석 보고서 DOCX 템플릿]
...
4. 근본 원인 분석(Root Cause Analysis)
   4.1 원인 요약
       {{see_why.summary}}

   4.2 상세 분석
       {{see_why.detailed_explanation}}

   4.3 주요 재무 지표
       {{see_why.key_figures_table}}

   4.4 반사실 분석
       "만약 {{counterfactual.variable_label}}이(가) {{counterfactual.cf_value}}였다면,
        {{counterfactual.outcome}}"

   4.5 시사점 및 제언
       {{see_why.recommendations}}

   [주의] 본 분석은 AI 기반 통계 분석 결과이며, 최종 판단은 전문가의 검토가 필요합니다.
...
```

---

## 결정 사항 (Decisions)

- LLM은 번역기 역할만 수행 (판단/계산 금지)
- Temperature 0으로 재현성 확보
- 5-Block 프롬프트 패턴 사용 (Axiom 표준)
- 수치 검증 필수 (post-processing)

## 금지 사항 (Forbidden)

- LLM에 원시 데이터(개인정보, 금액 상세) 전달
- LLM 출력을 검증 없이 보고서에 삽입
- confidence < 0.70인 경우 설명문 생성
- 법적 판단을 포함하는 설명문 생성

## 필수 사항 (Required)

- 모든 수치에 출처 표기
- confidence에 따른 한계 고지문 포함
- 생성된 설명문의 수치 일관성 검증
- 분석 보고서 삽입 전 HITL 검토

<!-- affects: 02_api/root-cause-api.md, 01_architecture/root-cause-engine.md -->
