"""G16: 도메인 레이어 NL2SQL 모드 API.

NL2SQL 쿼리 시 domain_mode=true이면 ObjectType/MaterializedView만 쿼리 대상으로 제한한다.
기존 Oracle NL2SQL 엔진의 서브스키마 필터링 확장.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("axiom.oracle.api.domain_mode")

router = APIRouter(prefix="/api/v3/oracle/domain-mode", tags=["도메인 NL2SQL"])


# ── 모델 ── #

class DomainModeConfig(BaseModel):
    """도메인 모드 설정"""
    enabled: bool = False
    allowed_object_types: list[str] = Field(
        default_factory=lambda: ["TABLE", "VIEW", "MATERIALIZED_VIEW"],
    )
    # 도메인 모드 활성화 시 MaterializedView + ObjectType만 허용
    domain_filter_types: list[str] = Field(
        default_factory=lambda: ["MATERIALIZED_VIEW", "OBJECT_TYPE"],
    )
    excluded_schemas: list[str] = Field(
        default_factory=lambda: ["pg_catalog", "information_schema", "pg_internal"],
    )


class DomainModeStatus(BaseModel):
    """도메인 모드 현재 상태"""
    enabled: bool = False
    available_tables: int = 0
    filtered_tables: int = 0
    config: DomainModeConfig = Field(default_factory=DomainModeConfig)


# ── 저장소 (테넌트별 설정) ── #

_tenant_configs: dict[str, DomainModeConfig] = {}


# ── 엔드포인트 ── #

@router.get("/status")
async def get_domain_mode_status(req: Request) -> dict:
    """현재 도메인 모드 상태 조회"""
    tenant_id = getattr(req.state, "tenant_id", "default")
    config = _tenant_configs.get(tenant_id, DomainModeConfig())

    return {
        "success": True,
        "data": DomainModeStatus(
            enabled=config.enabled,
            config=config,
        ).model_dump(),
    }


@router.post("/toggle")
async def toggle_domain_mode(
    req: Request,
    enabled: bool = True,
) -> dict:
    """도메인 모드 토글 — NL2SQL에서 ObjectType/MV만 쿼리 대상"""
    tenant_id = getattr(req.state, "tenant_id", "default")
    config = _tenant_configs.setdefault(tenant_id, DomainModeConfig())
    config.enabled = enabled

    logger.info("도메인 모드 변경: tenant=%s, enabled=%s", tenant_id, enabled)

    return {
        "success": True,
        "data": {"enabled": config.enabled, "tenant_id": tenant_id},
    }


@router.put("/config")
async def update_domain_mode_config(
    req: Request,
    config: DomainModeConfig,
) -> dict:
    """도메인 모드 상세 설정 변경"""
    tenant_id = getattr(req.state, "tenant_id", "default")
    _tenant_configs[tenant_id] = config

    return {
        "success": True,
        "data": config.model_dump(),
    }
