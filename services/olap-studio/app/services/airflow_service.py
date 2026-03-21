"""Airflow 연동 서비스 — ETL 파이프라인을 Airflow DAG로 변환/배포/실행한다.

KAIR의 airflow_service.py를 참조하여 Axiom 패턴으로 이식.

기능:
  - ETL 파이프라인 -> Python DAG 코드 생성
  - Airflow REST API를 통한 DAG 트리거
  - DAG 실행 상태 조회
  - DAG 목록 조회
"""
from __future__ import annotations

import json
import re
import textwrap
from datetime import datetime

import httpx
import structlog

from app.core.config import settings


def _sanitize_for_code(text: str) -> str:
    """코드 생성 시 인젝션 방지를 위해 안전하지 않은 문자를 제거한다.

    영숫자, 한글, 공백, 언더스코어, 하이픈, 마침표만 허용하고
    최대 200자로 제한한다.
    """
    return re.sub(r'[^a-zA-Z0-9가-힣 _\-.]', '', text)[:200]

logger = structlog.get_logger(__name__)


# ─── Airflow API 인증 헬퍼 ─────────────────────────────────

def _auth() -> tuple[str, str]:
    """Airflow 기본 인증 자격 증명을 반환한다."""
    return (settings.AIRFLOW_USER, settings.AIRFLOW_PASSWORD)


def _base_url() -> str:
    """Airflow REST API 기본 URL을 반환한다 (후행 슬래시 제거)."""
    return settings.AIRFLOW_BASE_URL.rstrip("/")


# ─── DAG 코드 생성 ────────────────────────────────────────

def generate_dag_code(
    pipeline_id: str,
    pipeline_name: str,
    pipeline_type: str,
    source_config: dict,
    target_config: dict,
    transform_spec: dict,
    schedule: str | None = None,
) -> tuple[str, str]:
    """ETL 파이프라인 정의에서 Airflow DAG Python 코드를 생성한다.

    생성되는 DAG 구조:
      start >> extract >> transform >> load >> notify >> end

    Args:
        pipeline_id: 파이프라인 UUID 문자열
        pipeline_name: 사람이 읽을 수 있는 이름
        pipeline_type: 파이프라인 유형 (FULL_LOAD, INCREMENTAL 등)
        source_config: 원천 데이터 연결 설정
        target_config: 대상 테이블 적재 설정
        transform_spec: 변환 규칙 (컬럼 매핑 등)
        schedule: cron 표현식 (None이면 수동 실행만)

    Returns:
        (dag_code, dag_id) 튜플
    """
    # DAG ID는 Airflow 규격에 맞게 영숫자+언더스코어로 제한
    dag_id = f"olap_etl_{pipeline_id.replace('-', '_')[:32]}"
    schedule_str = f"'{schedule}'" if schedule else "None"

    # 인젝션 방지: 이름은 sanitize, 설정값은 repr()로 안전하게 직렬화
    safe_pipeline_name = _sanitize_for_code(pipeline_name)
    safe_pipeline_type = _sanitize_for_code(pipeline_type)
    source_config_repr = repr(json.dumps(source_config, ensure_ascii=False))
    target_config_repr = repr(json.dumps(target_config, ensure_ascii=False))
    transform_config_repr = repr(json.dumps(transform_spec, ensure_ascii=False))

    code = textwrap.dedent(f'''\
    """
    자동 생성된 Airflow DAG — OLAP Studio ETL 파이프라인
    파이프라인: {safe_pipeline_name}
    ID: {pipeline_id}
    생성 시각: {datetime.utcnow().isoformat()}
    """
    import json
    from datetime import datetime, timedelta
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    from airflow.operators.empty import EmptyOperator

    default_args = {{
        "owner": "olap-studio",
        "depends_on_past": False,
        "email_on_failure": False,
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    }}

    dag = DAG(
        dag_id="{dag_id}",
        default_args=default_args,
        description="OLAP Studio ETL: {safe_pipeline_name}",
        schedule_interval={schedule_str},
        start_date=datetime(2026, 1, 1),
        catchup=False,
        tags=["olap-studio", "etl", "{safe_pipeline_type.lower()}"],
    )

    def extract_task(**kwargs):
        """원천 데이터 추출."""
        source_config = json.loads({source_config_repr})
        print(f"Extracting from: {{source_config}}")
        # TODO: 실제 추출 로직 (asyncpg 연결, 쿼리 실행)
        return {{"status": "extracted", "rows": 0}}

    def transform_task(**kwargs):
        """데이터 변환."""
        transform_spec = json.loads({transform_config_repr})
        ti = kwargs["ti"]
        extract_result = ti.xcom_pull(task_ids="extract")
        print(f"Transforming: {{extract_result}}")
        # TODO: 실제 변환 로직 (컬럼 매핑, 타입 변환)
        return {{"status": "transformed", "rows": 0}}

    def load_task(**kwargs):
        """대상 테이블 적재."""
        target_config = json.loads({target_config_repr})
        ti = kwargs["ti"]
        transform_result = ti.xcom_pull(task_ids="transform")
        print(f"Loading to: {{target_config}}")
        # TODO: 실제 적재 로직 (INSERT/UPSERT)
        return {{"status": "loaded", "rows": 0}}

    def notify_task(**kwargs):
        """완료 알림 — OLAP Studio 이벤트 발행."""
        print("ETL 완료 — 이벤트 발행")
        # TODO: OLAP Studio callback API 호출

    with dag:
        start = EmptyOperator(task_id="start")
        extract = PythonOperator(task_id="extract", python_callable=extract_task)
        transform = PythonOperator(task_id="transform", python_callable=transform_task)
        load = PythonOperator(task_id="load", python_callable=load_task)
        notify = PythonOperator(task_id="notify", python_callable=notify_task)
        end = EmptyOperator(task_id="end")

        start >> extract >> transform >> load >> notify >> end
    ''')

    return code, dag_id


# ─── Airflow REST API 연동 ─────────────────────────────────

async def trigger_dag(dag_id: str, conf: dict | None = None) -> dict:
    """Airflow DAG를 트리거한다.

    POST /api/v1/dags/{dag_id}/dagRuns

    Airflow가 미설정이거나 연결 불가 시 에러 딕셔너리를 반환한다.
    """
    base = _base_url()
    if not base:
        return {"error": "AIRFLOW_BASE_URL이 설정되지 않았습니다", "success": False}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{base}/api/v1/dags/{dag_id}/dagRuns",
                json={"conf": conf or {}},
                auth=_auth(),
            )
            if response.status_code in (200, 201):
                data = response.json()
                logger.info(
                    "airflow_dag_triggered",
                    dag_id=dag_id,
                    run_id=data.get("dag_run_id"),
                )
                return {"success": True, "data": data}
            else:
                logger.warning(
                    "airflow_trigger_failed",
                    status=response.status_code,
                    body=response.text[:200],
                )
                return {
                    "success": False,
                    "error": f"Airflow 응답: {response.status_code}",
                }
    except httpx.ConnectError:
        logger.warning("airflow_unreachable", base_url=base)
        return {"success": False, "error": "Airflow 서버에 연결할 수 없습니다"}
    except Exception as e:
        logger.warning("airflow_trigger_error", error=str(e))
        return {"success": False, "error": str(e)}


async def get_dag_status(dag_id: str) -> dict:
    """DAG 상태 및 최근 실행 정보를 조회한다.

    두 가지 API를 병렬 호출한다:
      - GET /api/v1/dags/{dag_id}         — DAG 기본 정보
      - GET /api/v1/dags/{dag_id}/dagRuns  — 최근 5개 실행 이력
    """
    base = _base_url()
    if not base:
        return {"error": "AIRFLOW_BASE_URL이 설정되지 않았습니다"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # DAG 기본 정보
            dag_resp = await client.get(
                f"{base}/api/v1/dags/{dag_id}",
                auth=_auth(),
            )
            dag_info = dag_resp.json() if dag_resp.status_code == 200 else {}

            # 최근 실행 목록
            runs_resp = await client.get(
                f"{base}/api/v1/dags/{dag_id}/dagRuns",
                params={"limit": 5, "order_by": "-start_date"},
                auth=_auth(),
            )
            runs = (
                runs_resp.json().get("dag_runs", [])
                if runs_resp.status_code == 200
                else []
            )

            return {
                "dag_id": dag_id,
                "is_paused": dag_info.get("is_paused", True),
                "is_active": dag_info.get("is_active", False),
                "schedule": dag_info.get("schedule_interval"),
                "recent_runs": [
                    {
                        "run_id": r.get("dag_run_id", ""),
                        "state": r.get("state", "unknown"),
                        "start_date": r.get("start_date"),
                        "end_date": r.get("end_date"),
                    }
                    for r in runs
                ],
            }
    except httpx.ConnectError:
        logger.warning("airflow_unreachable", base_url=base)
        return {"error": "Airflow 서버에 연결할 수 없습니다"}
    except Exception as e:
        logger.warning("airflow_status_error", error=str(e))
        return {"error": str(e)}


async def list_dags(tag: str = "olap-studio") -> list[dict]:
    """OLAP Studio 태그가 있는 DAG 목록을 조회한다.

    GET /api/v1/dags?tags=olap-studio&limit=100
    """
    base = _base_url()
    if not base:
        return []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{base}/api/v1/dags",
                params={"tags": tag, "limit": 100},
                auth=_auth(),
            )
            if response.status_code == 200:
                dags = response.json().get("dags", [])
                return [
                    {
                        "dag_id": d.get("dag_id", ""),
                        "description": d.get("description", ""),
                        "is_paused": d.get("is_paused", True),
                        "is_active": d.get("is_active", False),
                        "schedule": d.get("schedule_interval"),
                        "tags": [t.get("name", "") for t in d.get("tags", [])],
                    }
                    for d in dags
                ]
            return []
    except httpx.ConnectError:
        logger.warning("airflow_unreachable", base_url=base)
        return []
    except Exception as e:
        logger.warning("airflow_list_error", error=str(e))
        return []
