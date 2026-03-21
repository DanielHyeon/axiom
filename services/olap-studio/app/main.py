"""OLAP Studio — Axiom OLAP/ETL/큐브 마이크로서비스."""
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import configure_logging, get_logger
from app.core.error_handler import register_error_handlers
from app.core.middleware import TenantMiddleware
from app.core.metrics_middleware import MetricsMiddleware
from app.core.database import get_pool, close_pool
from app.core.telemetry import setup_telemetry
from app.api.datasource import router as datasource_router
from app.api.model import router as model_router
from app.api.cube import router as cube_router
from app.api.pivot import router as pivot_router
from app.api.etl import router as etl_router
from app.api.lineage import router as lineage_router
from app.api.ai_generation import router as ai_router
from app.api.nl2sql import router as nl2sql_router
from app.api.integration import router as integration_router
from app.api.airflow import router as airflow_router
from app.events.outbox import OlapRelayWorker, ensure_outbox_table, close_redis

logger = get_logger(__name__)

# Relay 워커 백그라운드 태스크 참조
_relay_task: asyncio.Task | None = None
_relay_worker: OlapRelayWorker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서비스 시작/종료 시 리소스 관리."""
    global _relay_task, _relay_worker

    # structlog 초기화 — 다른 모듈이 로거를 사용하기 전에 설정
    configure_logging(json_format=settings.ENVIRONMENT != "development")

    # OpenTelemetry 분산 추적 초기화 (패키지 미설치 시 no-op)
    setup_telemetry("olap-studio")

    logger.info("olap_studio_startup", environment=settings.ENVIRONMENT)
    # DB 풀 워밍업
    await get_pool()

    # Outbox 테이블 DDL 보장
    await ensure_outbox_table()

    # Relay 워커 시작 — Redis 미설정 시에도 안전하게 동작
    _relay_worker = OlapRelayWorker(poll_interval=5, max_batch=100)
    _relay_task = asyncio.create_task(_relay_worker.run())

    yield

    # 종료 시퀀스: Relay 워커 → Redis → DB 풀
    logger.info("olap_studio_shutdown")
    if _relay_worker is not None:
        _relay_worker.shutdown()
    if _relay_task is not None and not _relay_task.done():
        _relay_task.cancel()
        try:
            await _relay_task
        except asyncio.CancelledError:
            pass
    await close_redis()
    await close_pool()


app = FastAPI(
    title="Axiom OLAP Studio",
    version="1.0.0",
    description="스타 스키마 OLAP 피벗 · 큐브 관리 · ETL · 리니지",
    lifespan=lifespan,
)

# 전역 예외 핸들러 등록 — 모든 에러를 Axiom 표준 포맷으로 변환
register_error_handlers(app)

# 미들웨어 (순서 주의: 마지막 추가 = 먼저 실행)
app.add_middleware(TenantMiddleware)
app.add_middleware(MetricsMiddleware)  # 요청 시간 측정 — 모든 미들웨어를 감싸도록 TenantMiddleware 다음에 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(datasource_router)
app.include_router(model_router)
app.include_router(cube_router)
app.include_router(pivot_router)
app.include_router(etl_router)
app.include_router(lineage_router)
app.include_router(ai_router)
app.include_router(nl2sql_router)
app.include_router(integration_router)
app.include_router(airflow_router)


@app.get("/health/live")
async def health_live():
    """라이브니스 프로브 — 프로세스 생존 확인."""
    return {"status": "alive"}


@app.get("/health")
async def health_check():
    """레디니스 프로브 — DB 연결 확인."""
    db_status = "unreachable"
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            db_status = "healthy"
    except Exception:
        pass

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "checks": {"database": db_status == "healthy"},
        "version": "1.0.0",
    }
