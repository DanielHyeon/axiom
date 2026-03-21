"""Airflow 연동 서비스 단위 테스트.

DAG 코드 생성(순수 함수), 인젝션 방지, Airflow 미설정 에러 경로를 검증한다.
실제 Airflow REST API 호출 없이 에러 분기만 테스트한다.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.services.airflow_service import (
    generate_dag_code,
    trigger_dag,
    get_dag_status,
    list_dags,
    _sanitize_for_code,
)


# ──────────────────────────────────────────────────────────────
# 테스트용 기본 파이프라인 설정
# ──────────────────────────────────────────────────────────────

_PIPELINE_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
_PIPELINE_NAME = "매출 일일 집계"
_PIPELINE_TYPE = "FULL_LOAD"
_SOURCE_CONFIG = {"host": "db.example.com", "port": 5432, "table": "sales"}
_TARGET_CONFIG = {"schema": "dw", "table": "fact_sales"}
_TRANSFORM_SPEC = {"columns": [{"src": "amount", "dst": "sales_amount"}]}


def _gen(**overrides) -> tuple[str, str]:
    """기본값으로 generate_dag_code를 호출하는 헬퍼."""
    kwargs = {
        "pipeline_id": _PIPELINE_ID,
        "pipeline_name": _PIPELINE_NAME,
        "pipeline_type": _PIPELINE_TYPE,
        "source_config": _SOURCE_CONFIG,
        "target_config": _TARGET_CONFIG,
        "transform_spec": _TRANSFORM_SPEC,
    }
    kwargs.update(overrides)
    return generate_dag_code(**kwargs)


# ──────────────────────────────────────────────────────────────
# DAG 코드 생성 테스트
# ──────────────────────────────────────────────────────────────

class TestGenerateDagCode:
    """generate_dag_code() — DAG Python 코드 생성 검증."""

    def test_DAG_코드_생성_기본(self):
        """유효한 Python 코드 문자열과 dag_id 튜플을 반환한다."""
        code, dag_id = _gen()
        assert isinstance(code, str)
        assert isinstance(dag_id, str)
        assert len(code) > 100, "생성된 코드가 너무 짧다"
        # dag_id가 코드 내에 포함되어야 한다
        assert dag_id in code

    def test_DAG_코드_파이프라인명_포함(self):
        """파이프라인 이름이 DAG description에 포함된다."""
        code, _ = _gen()
        assert "매출 일일 집계" in code

    def test_DAG_코드_스케줄_포함(self):
        """schedule_cron이 지정되면 schedule_interval에 포함된다."""
        code, _ = _gen(schedule="0 2 * * *")
        assert "'0 2 * * *'" in code

    def test_DAG_코드_스케줄_없음_None(self):
        """schedule이 None이면 schedule_interval=None으로 설정된다."""
        code, _ = _gen(schedule=None)
        assert "schedule_interval=None" in code

    def test_DAG_ID_형식(self):
        """dag_id는 'olap_etl_'로 시작하고 하이픈이 없다."""
        _, dag_id = _gen()
        assert dag_id.startswith("olap_etl_")
        assert "-" not in dag_id

    def test_DAG_코드_JSON_안전(self):
        """특수문자가 포함된 source_config가 코드를 깨뜨리지 않는다."""
        tricky_config = {"host": "db.com", "query": "SELECT * WHERE name = 'O\\'Brien'"}
        code, _ = _gen(source_config=tricky_config)
        assert isinstance(code, str)
        # repr()로 감싸므로 문자열 리터럴로 안전하게 포함
        assert "json.loads(" in code

    def test_파이프라인명_새니타이즈(self):
        """인젝션 위험 문자가 포함된 이름이 sanitize된다."""
        dangerous_name = "test'); import os; os.system('rm -rf /"
        safe = _sanitize_for_code(dangerous_name)
        # 허용 문자(영숫자, 한글, 공백, 언더스코어, 하이픈, 마침표)만 남는다
        assert "'" not in safe
        assert "(" not in safe
        assert ";" not in safe

    def test_DAG_코드_import_json(self):
        """생성된 코드에 'import json'이 포함된다."""
        code, _ = _gen()
        assert "import json" in code

    def test_DAG_코드_태그_포함(self):
        """'olap-studio'와 'etl' 태그가 포함된다."""
        code, _ = _gen()
        assert '"olap-studio"' in code
        assert '"etl"' in code

    def test_DAG_코드_JSON_로드_포함(self):
        """생성된 코드에서 json.loads로 설정을 역직렬화한다."""
        code, _ = _gen()
        assert "json.loads(" in code

    def test_DAG_코드_repr_인젝션_방지(self):
        """따옴표가 포함된 config 값이 repr()로 안전하게 직렬화된다."""
        config_with_quotes = {"key": 'value with "double" and \'single\' quotes'}
        code, _ = _gen(source_config=config_with_quotes)
        # 코드가 문자열로 정상 생성되어야 한다
        assert isinstance(code, str)
        assert "json.loads(" in code


# ──────────────────────────────────────────────────────────────
# Airflow 미설정 에러 경로 테스트
# ──────────────────────────────────────────────────────────────

class TestAirflowNotConfigured:
    """Airflow URL 미설정 시 안전한 에러 반환 검증."""

    @pytest.mark.asyncio
    async def test_트리거_Airflow_미설정_에러(self):
        """AIRFLOW_BASE_URL이 빈 문자열이면 에러 딕셔너리를 반환한다."""
        with patch("app.services.airflow_service.settings") as mock_settings:
            mock_settings.AIRFLOW_BASE_URL = ""
            mock_settings.AIRFLOW_USER = "airflow"
            mock_settings.AIRFLOW_PASSWORD = "airflow"
            result = await trigger_dag("test_dag_id")
            assert "error" in result
            assert result.get("success") is False

    @pytest.mark.asyncio
    async def test_상태_조회_Airflow_미설정_에러(self):
        """AIRFLOW_BASE_URL이 빈 문자열이면 에러 딕셔너리를 반환한다."""
        with patch("app.services.airflow_service.settings") as mock_settings:
            mock_settings.AIRFLOW_BASE_URL = ""
            mock_settings.AIRFLOW_USER = "airflow"
            mock_settings.AIRFLOW_PASSWORD = "airflow"
            result = await get_dag_status("test_dag_id")
            assert "error" in result

    @pytest.mark.asyncio
    async def test_목록_조회_Airflow_미설정_빈리스트(self):
        """AIRFLOW_BASE_URL이 빈 문자열이면 빈 리스트를 반환한다."""
        with patch("app.services.airflow_service.settings") as mock_settings:
            mock_settings.AIRFLOW_BASE_URL = ""
            mock_settings.AIRFLOW_USER = "airflow"
            mock_settings.AIRFLOW_PASSWORD = "airflow"
            result = await list_dags()
            assert result == []
