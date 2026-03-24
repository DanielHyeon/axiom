"""
시멘틱 스냅샷 서비스 — 릴리스 기반 immutable 런타임 스냅샷 생성/관리

런타임 소비자(Oracle, Canvas)가 매 요청마다 여러 API를 호출하지 않도록
시멘틱 계약 전체를 하나의 immutable 스냅샷으로 물질화(materialize)한다.

4개 테이블:
  - semantic_snapshots: 스냅샷 헤더 (버전, 릴리스, 상태, 매니페스트)
  - semantic_snapshot_artifacts: 분리 저장된 아티팩트 (CONTRACT_INDEX, JOIN_GRAPH 등)
  - semantic_runtime_bindings: 소비자(Oracle 등)의 바인딩 정보
  - semantic_snapshot_leases: 요청 단위 낙관적 임대 (동시성 제어)
"""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog

from app.core.config import settings
from app.services.semantic_store import SemanticStore

logger = structlog.get_logger()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


def _import_psycopg2():
    """psycopg2 동적 임포트 — 경로 문제 방어"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2, RealDictCursor
    except Exception:
        for path in ("/usr/lib/python3/dist-packages", "/home/daniel/.local/lib/python3.12/site-packages"):
            if path not in sys.path:
                sys.path.append(path)
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2, RealDictCursor


# ── 스냅샷 상태 상수 ──
SNAPSHOT_BUILDING = "BUILDING"
SNAPSHOT_READY = "READY"
SNAPSHOT_ACTIVE = "ACTIVE"
SNAPSHOT_INVALIDATED = "INVALIDATED"
VALID_SNAPSHOT_STATUSES = {SNAPSHOT_BUILDING, SNAPSHOT_READY, SNAPSHOT_ACTIVE, SNAPSHOT_INVALIDATED}

# ── 임대 상태 상수 ──
LEASE_ACTIVE = "ACTIVE"
LEASE_RELEASED = "RELEASED"
LEASE_EXPIRED = "EXPIRED"

# ── 아티팩트 유형 상수 ──
ARTIFACT_CONTRACT_INDEX = "CONTRACT_INDEX"
ARTIFACT_JOIN_GRAPH = "JOIN_GRAPH"
ARTIFACT_CONTEXT_PACKS = "CONTEXT_PACKS"
ARTIFACT_SYNONYM_MAP = "SYNONYM_MAP"


def _compute_content_hash(data: Any) -> str:
    """JSON 직렬화 후 MD5 해시 계산 — 결정론적 정렬"""
    serialized = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.md5(serialized.encode("utf-8")).hexdigest()


# ── 스냅샷 변경 비교 설정 ──
# 각 아티팩트 유형별로 비교 대상 컬렉션과 식별 키를 정의한다.
# 예: CONTRACT_INDEX 아티팩트의 "entities" 컬렉션은 "id" 필드로 개별 항목을 식별.
DIFF_CONFIG: dict[str, dict[str, str]] = {
    ARTIFACT_CONTRACT_INDEX: {
        "entities": "id",
        "measures": "name",
        "dimensions": "name",
        "quality_contracts": "id",
    },
    ARTIFACT_JOIN_GRAPH: {
        "allowed_joins": "id",
        "banned_joins": "id",
    },
    ARTIFACT_CONTEXT_PACKS: {
        "packs": "intent_type",
    },
    ARTIFACT_SYNONYM_MAP: {
        "alias_groups": "id",
    },
}


def _canonical_sort(items: list[dict], key_field: str) -> list[dict]:
    """리스트를 식별 키 기준으로 정렬한다 — 순서 변경을 변경으로 오탐하지 않기 위해."""
    return sorted(items, key=lambda x: str(x.get(key_field, "")))


def _diff_fields(prev_item: dict, curr_item: dict) -> list[str]:
    """두 딕셔너리를 비교하여 값이 다른 필드 이름 목록을 반환한다."""
    all_keys = set(prev_item.keys()) | set(curr_item.keys())
    changed: list[str] = []
    for k in sorted(all_keys):
        # JSON 직렬화로 비교 — datetime 등 타입 차이에 안전
        prev_val = json.dumps(prev_item.get(k), sort_keys=True, default=str)
        curr_val = json.dumps(curr_item.get(k), sort_keys=True, default=str)
        if prev_val != curr_val:
            changed.append(k)
    return changed


def _compute_snapshot_changes(
    prev_artifacts: dict[str, dict],
    curr_artifacts: dict[str, dict],
) -> list[dict]:
    """두 스냅샷의 아티팩트를 비교하여 변경 목록을 생성한다.

    각 아티팩트 유형 안의 컬렉션별로 개별 항목을 식별 키로 매칭하여
    Add / Change / Delete 를 판별한다.

    Args:
        prev_artifacts: 이전 스냅샷의 아티팩트 {artifact_type: artifact_json, ...}
        curr_artifacts: 현재 스냅샷의 아티팩트 {artifact_type: artifact_json, ...}

    Returns:
        [{"type": "Add|Change|Delete", "artifact": "CONTRACT_INDEX",
          "collection": "entities", "name": "...", "changed_fields": ["sql_expression"]}]
    """
    changes: list[dict] = []

    for artifact_type, collections in DIFF_CONFIG.items():
        prev_data = prev_artifacts.get(artifact_type, {})
        curr_data = curr_artifacts.get(artifact_type, {})

        for collection_name, id_field in collections.items():
            # 컬렉션 꺼내기 (없으면 빈 리스트)
            prev_items = prev_data.get(collection_name, [])
            curr_items = curr_data.get(collection_name, [])

            # dict가 아닌 리스트만 비교 대상 — dict인 경우(synonym_map 등) 리스트로 변환
            if isinstance(prev_items, dict):
                prev_items = list(prev_items.values()) if prev_items else []
            if isinstance(curr_items, dict):
                curr_items = list(curr_items.values()) if curr_items else []

            # 정렬하여 순서 변경을 무시
            prev_sorted = _canonical_sort(prev_items, id_field)
            curr_sorted = _canonical_sort(curr_items, id_field)

            # 식별 키로 인덱싱
            prev_map = {str(item.get(id_field, "")): item for item in prev_sorted}
            curr_map = {str(item.get(id_field, "")): item for item in curr_sorted}

            prev_keys = set(prev_map.keys())
            curr_keys = set(curr_map.keys())

            # 삭제된 항목
            for key in sorted(prev_keys - curr_keys):
                changes.append({
                    "type": "Delete",
                    "artifact": artifact_type,
                    "collection": collection_name,
                    "name": key,
                    "changed_fields": [],
                })

            # 추가된 항목
            for key in sorted(curr_keys - prev_keys):
                changes.append({
                    "type": "Add",
                    "artifact": artifact_type,
                    "collection": collection_name,
                    "name": key,
                    "changed_fields": [],
                })

            # 변경된 항목 (양쪽에 모두 존재하는 키)
            for key in sorted(prev_keys & curr_keys):
                changed_fields = _diff_fields(prev_map[key], curr_map[key])
                if changed_fields:
                    changes.append({
                        "type": "Change",
                        "artifact": artifact_type,
                        "collection": collection_name,
                        "name": key,
                        "changed_fields": changed_fields,
                    })

    return changes


class SnapshotBuilder:
    """릴리스 기반 스냅샷을 빌드한다 — 계약/온톨로지/품질/AI 컨텍스트 통합"""

    def __init__(self, store: SemanticStore, database_url: str | None = None):
        self._store = store
        self._database_url = database_url or settings.SCHEMA_EDIT_DATABASE_URL
        self._DB_SCHEMA = "synapse"

    def _connect(self):
        psycopg2, _ = _import_psycopg2()
        conn = psycopg2.connect(self._database_url)
        cur = conn.cursor()
        cur.execute(f"SET search_path TO {self._DB_SCHEMA}, public")
        cur.close()
        return conn

    def _dict_cursor(self):
        _, RealDictCursor = _import_psycopg2()
        return RealDictCursor

    def build_from_release(
        self,
        tenant_id: str,
        release_id: str | None = None,
        release_version: str | None = None,
        created_by: str = "system",
    ) -> dict[str, Any]:
        """현재 활성 데이터를 기반으로 스냅샷을 생성한다.

        1. get_ai_context() 결과를 스냅샷 페이로드로 사용
        2. content_hash 계산 (JSON 직렬화 → MD5)
        3. semantic_snapshots 테이블에 INSERT
        4. artifact 분리 저장 (CONTRACT_INDEX, JOIN_GRAPH, CONTEXT_PACKS, SYNONYM_MAP)
        5. status = 'READY' 로 업데이트
        """
        # 1) AI 컨텍스트 수집 — 스냅샷 페이로드의 원천
        ai_context = self._store.get_ai_context(tenant_id)

        # 2) 콘텐츠 해시 계산
        content_hash = _compute_content_hash(ai_context)

        # 3) 스냅샷 버전 생성 (타임스탬프 + 해시 앞 8자리)
        now = _now_dt()
        snapshot_version = f"snap-{now.strftime('%Y%m%d%H%M%S')}-{content_hash[:8]}"
        snapshot_id = _uuid()

        # 매니페스트 — 스냅샷 요약 정보
        manifest = {
            "summary": ai_context.get("summary", {}),
            "context_type": ai_context.get("context_type", "semantic_contract"),
            "approved_only": ai_context.get("approved_only", True),
            "tenant_id": tenant_id,
        }

        conn = self._connect()
        cur = conn.cursor()
        try:
            # 4) semantic_snapshots 레코드 삽입 (status=BUILDING)
            cur.execute("""
                INSERT INTO semantic_snapshots (
                    id, snapshot_version, release_id, release_version,
                    status, manifest_json, content_hash,
                    built_at, created_by, tenant_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                snapshot_id, snapshot_version,
                release_id or "", release_version or "",
                SNAPSHOT_BUILDING,
                json.dumps(manifest, default=str),
                content_hash,
                now, created_by, tenant_id,
            ))

            # 5) 아티팩트 분리 저장
            artifacts = self._split_artifacts(snapshot_id, ai_context)
            for art in artifacts:
                cur.execute("""
                    INSERT INTO semantic_snapshot_artifacts (
                        id, snapshot_id, artifact_type, artifact_key,
                        artifact_json, artifact_hash, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    _uuid(), snapshot_id,
                    art["artifact_type"], art["artifact_key"],
                    json.dumps(art["artifact_json"], default=str),
                    art["artifact_hash"], now,
                ))

            # 6) status → READY 업데이트
            cur.execute("""
                UPDATE semantic_snapshots
                SET status = %s
                WHERE id = %s
            """, (SNAPSHOT_READY, snapshot_id))

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

        logger.info(
            "semantic_snapshot_built",
            snapshot_id=snapshot_id,
            snapshot_version=snapshot_version,
            content_hash=content_hash,
            artifact_count=len(artifacts),
            tenant_id=tenant_id,
        )

        return {
            "snapshot_id": snapshot_id,
            "snapshot_version": snapshot_version,
            "release_id": release_id or "",
            "release_version": release_version or "",
            "status": SNAPSHOT_READY,
            "content_hash": content_hash,
            "manifest": manifest,
            "artifact_count": len(artifacts),
            "built_at": now.isoformat(),
        }

    def _split_artifacts(
        self, snapshot_id: str, ai_context: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """AI 컨텍스트를 4종 아티팩트로 분리한다.

        - CONTRACT_INDEX: 엔티티 + 지표 + 차원 인덱스
        - JOIN_GRAPH: 허용/금지 조인 그래프
        - CONTEXT_PACKS: AI 컨텍스트 팩 (있으면)
        - SYNONYM_MAP: 용어 동의어 맵
        """
        artifacts: list[dict[str, Any]] = []

        # CONTRACT_INDEX — 엔티티, 지표, 차원 통합 인덱스
        contract_index = {
            "entities": ai_context.get("entities", []),
            "measures": ai_context.get("measures", []),
            "dimensions": ai_context.get("dimensions", []),
            "quality_contracts": ai_context.get("quality_contracts", []),
        }
        artifacts.append({
            "artifact_type": ARTIFACT_CONTRACT_INDEX,
            "artifact_key": "default",
            "artifact_json": contract_index,
            "artifact_hash": _compute_content_hash(contract_index),
        })

        # JOIN_GRAPH — 허용 조인 + 금지 조인
        join_graph = {
            "allowed_joins": ai_context.get("allowed_joins", []),
            "banned_joins": ai_context.get("banned_joins", []),
        }
        artifacts.append({
            "artifact_type": ARTIFACT_JOIN_GRAPH,
            "artifact_key": "default",
            "artifact_json": join_graph,
            "artifact_hash": _compute_content_hash(join_graph),
        })

        # CONTEXT_PACKS — AI 컨텍스트 팩 (존재 시)
        context_packs = ai_context.get("context_packs", [])
        artifacts.append({
            "artifact_type": ARTIFACT_CONTEXT_PACKS,
            "artifact_key": "default",
            "artifact_json": {"packs": context_packs},
            "artifact_hash": _compute_content_hash(context_packs),
        })

        # SYNONYM_MAP — 용어 동의어 맵
        synonym_map = ai_context.get("synonym_map", {})
        artifacts.append({
            "artifact_type": ARTIFACT_SYNONYM_MAP,
            "artifact_key": "default",
            "artifact_json": {"synonyms": synonym_map},
            "artifact_hash": _compute_content_hash(synonym_map),
        })

        return artifacts


class SnapshotRegistry:
    """스냅샷 조회/활성화/무효화/바인딩/임대 관리"""

    _DB_SCHEMA = "synapse"

    def __init__(self, database_url: str | None = None):
        self._database_url = database_url or settings.SCHEMA_EDIT_DATABASE_URL
        self._schema_ready = False

    def _connect(self):
        psycopg2, _ = _import_psycopg2()
        conn = psycopg2.connect(self._database_url)
        cur = conn.cursor()
        cur.execute(f"SET search_path TO {self._DB_SCHEMA}, public")
        cur.close()
        return conn

    def _dict_cursor(self):
        _, RealDictCursor = _import_psycopg2()
        return RealDictCursor

    # ── 스키마 초기화 (멱등) ──

    def ensure_schema(self) -> None:
        """스냅샷 관련 4개 테이블 생성 (CREATE IF NOT EXISTS)"""
        if self._schema_ready:
            return

        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self._DB_SCHEMA}")

            # 스냅샷 헤더
            cur.execute("""
                CREATE TABLE IF NOT EXISTS semantic_snapshots (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    snapshot_version VARCHAR(64) NOT NULL UNIQUE,
                    release_id VARCHAR NOT NULL DEFAULT '',
                    release_version VARCHAR(64) NOT NULL DEFAULT '',
                    status VARCHAR(20) NOT NULL DEFAULT 'BUILDING',
                    manifest_json JSONB NOT NULL DEFAULT '{}',
                    content_hash VARCHAR(128) NOT NULL DEFAULT '',
                    built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    activated_at TIMESTAMPTZ,
                    invalidated_at TIMESTAMPTZ,
                    invalidation_reason VARCHAR(100),
                    created_by VARCHAR(100) NOT NULL DEFAULT 'system',
                    tenant_id VARCHAR NOT NULL DEFAULT ''
                )
            """)

            # 스냅샷 아티팩트
            cur.execute("""
                CREATE TABLE IF NOT EXISTS semantic_snapshot_artifacts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    snapshot_id UUID NOT NULL REFERENCES semantic_snapshots(id),
                    artifact_type VARCHAR(50) NOT NULL,
                    artifact_key VARCHAR(200) NOT NULL DEFAULT 'default',
                    artifact_json JSONB NOT NULL,
                    artifact_hash VARCHAR(128) NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE(snapshot_id, artifact_type, artifact_key)
                )
            """)

            # 런타임 바인딩
            cur.execute("""
                CREATE TABLE IF NOT EXISTS semantic_runtime_bindings (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    consumer_name VARCHAR(50) NOT NULL,
                    consumer_instance_id VARCHAR(100) NOT NULL DEFAULT 'default',
                    bound_snapshot_version VARCHAR(64) NOT NULL,
                    bound_release_version VARCHAR(64) NOT NULL DEFAULT '',
                    binding_mode VARCHAR(20) NOT NULL DEFAULT 'AUTO',
                    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE(consumer_name, consumer_instance_id)
                )
            """)

            # 스냅샷 임대
            cur.execute("""
                CREATE TABLE IF NOT EXISTS semantic_snapshot_leases (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    request_id VARCHAR(100) NOT NULL,
                    consumer_name VARCHAR(50) NOT NULL,
                    snapshot_version VARCHAR(64) NOT NULL,
                    acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '30 minutes'),
                    released_at TIMESTAMPTZ,
                    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                    UNIQUE(request_id, consumer_name)
                )
            """)

            # 인덱스
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_snapshots_status
                    ON semantic_snapshots(tenant_id, status)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_snapshot_artifacts_snap
                    ON semantic_snapshot_artifacts(snapshot_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_runtime_bindings_consumer
                    ON semantic_runtime_bindings(consumer_name)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_snapshot_leases_status
                    ON semantic_snapshot_leases(status, expires_at)
            """)

            conn.commit()
            self._schema_ready = True
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    # ── 스냅샷 조회 ──

    def get_snapshot(self, snapshot_version: str) -> dict[str, Any] | None:
        """특정 버전의 스냅샷을 조회한다 (아티팩트 포함)"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        try:
            # 스냅샷 헤더
            cur.execute(
                "SELECT * FROM semantic_snapshots WHERE snapshot_version = %s",
                (snapshot_version,),
            )
            row = cur.fetchone()
            if not row:
                return None
            snapshot = dict(row)

            # 아티팩트 목록
            cur.execute(
                "SELECT * FROM semantic_snapshot_artifacts WHERE snapshot_id = %s ORDER BY artifact_type",
                (str(snapshot["id"]),),
            )
            snapshot["artifacts"] = [dict(a) for a in cur.fetchall()]
            return snapshot
        finally:
            cur.close()
            conn.close()

    def find_active(self, tenant_id: str, consumer_name: str | None = None) -> dict[str, Any] | None:
        """현재 활성(ACTIVE) 스냅샷을 반환한다.

        consumer_name이 주어지면 해당 소비자의 바인딩을 확인하고,
        없으면 가장 최근 ACTIVE 스냅샷을 반환한다.
        """
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        try:
            # 소비자 바인딩이 있으면 해당 버전 우선
            if consumer_name:
                cur.execute(
                    "SELECT bound_snapshot_version FROM semantic_runtime_bindings WHERE consumer_name = %s LIMIT 1",
                    (consumer_name,),
                )
                binding = cur.fetchone()
                if binding:
                    cur.execute(
                        "SELECT * FROM semantic_snapshots WHERE snapshot_version = %s AND tenant_id = %s",
                        (binding["bound_snapshot_version"], tenant_id),
                    )
                    row = cur.fetchone()
                    if row and row["status"] == SNAPSHOT_ACTIVE:
                        return dict(row)

            # 바인딩 없으면 최신 ACTIVE 스냅샷
            cur.execute(
                "SELECT * FROM semantic_snapshots WHERE status = %s AND tenant_id = %s ORDER BY activated_at DESC LIMIT 1",
                (SNAPSHOT_ACTIVE, tenant_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            cur.close()
            conn.close()

    def list_snapshots(self, tenant_id: str, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        """스냅샷 목록을 반환한다 (최신순)"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        try:
            cur.execute(
                "SELECT * FROM semantic_snapshots WHERE tenant_id = %s ORDER BY built_at DESC LIMIT %s OFFSET %s",
                (tenant_id, limit, offset),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    # ── 활성화 / 무효화 ──

    def activate(self, snapshot_version: str, tenant_id: str) -> dict[str, Any]:
        """스냅샷을 ACTIVE 상태로 전환한다.

        기존 ACTIVE 스냅샷은 READY로 강등된다.
        """
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        now = _now_dt()
        try:
            # 대상 스냅샷 확인
            cur.execute(
                "SELECT * FROM semantic_snapshots WHERE snapshot_version = %s AND tenant_id = %s",
                (snapshot_version, tenant_id),
            )
            target = cur.fetchone()
            if not target:
                raise KeyError(f"snapshot_version '{snapshot_version}'를 찾을 수 없습니다")
            if target["status"] == SNAPSHOT_INVALIDATED:
                raise ValueError("무효화된 스냅샷은 활성화할 수 없습니다")

            # 기존 ACTIVE → READY 강등
            cur.execute(
                "UPDATE semantic_snapshots SET status = %s WHERE status = %s AND tenant_id = %s",
                (SNAPSHOT_READY, SNAPSHOT_ACTIVE, tenant_id),
            )

            # 대상 활성화
            cur.execute(
                "UPDATE semantic_snapshots SET status = %s, activated_at = %s WHERE snapshot_version = %s",
                (SNAPSHOT_ACTIVE, now, snapshot_version),
            )
            conn.commit()

            result = dict(target)
            result["status"] = SNAPSHOT_ACTIVE
            result["activated_at"] = now

            logger.info("semantic_snapshot_activated", snapshot_version=snapshot_version, tenant_id=tenant_id)
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    def invalidate(self, snapshot_version: str, tenant_id: str, reason: str = "") -> dict[str, Any]:
        """스냅샷을 무효화한다 — 더 이상 소비할 수 없음"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        now = _now_dt()
        try:
            cur.execute(
                "SELECT * FROM semantic_snapshots WHERE snapshot_version = %s AND tenant_id = %s",
                (snapshot_version, tenant_id),
            )
            target = cur.fetchone()
            if not target:
                raise KeyError(f"snapshot_version '{snapshot_version}'를 찾을 수 없습니다")

            cur.execute(
                "UPDATE semantic_snapshots SET status = %s, invalidated_at = %s, invalidation_reason = %s WHERE snapshot_version = %s",
                (SNAPSHOT_INVALIDATED, now, reason, snapshot_version),
            )
            conn.commit()

            result = dict(target)
            result["status"] = SNAPSHOT_INVALIDATED
            result["invalidated_at"] = now
            result["invalidation_reason"] = reason

            logger.info("semantic_snapshot_invalidated", snapshot_version=snapshot_version, reason=reason)
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    # ── 소비자 바인딩 ──

    def register_binding(
        self,
        consumer_name: str,
        instance_id: str,
        snapshot_version: str,
        mode: str = "AUTO",
    ) -> dict[str, Any]:
        """소비자 바인딩을 등록/갱신한다 (heartbeat 용도)"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        now = _now_dt()
        binding_id = _uuid()
        try:
            # UPSERT — 기존 바인딩이 있으면 업데이트
            cur.execute("""
                INSERT INTO semantic_runtime_bindings (
                    id, consumer_name, consumer_instance_id,
                    bound_snapshot_version, binding_mode,
                    last_seen_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (consumer_name, consumer_instance_id)
                DO UPDATE SET
                    bound_snapshot_version = EXCLUDED.bound_snapshot_version,
                    binding_mode = EXCLUDED.binding_mode,
                    last_seen_at = EXCLUDED.last_seen_at,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
            """, (
                binding_id, consumer_name, instance_id,
                snapshot_version, mode, now, now,
            ))
            row = cur.fetchone()
            conn.commit()

            logger.info(
                "semantic_binding_registered",
                consumer_name=consumer_name,
                instance_id=instance_id,
                snapshot_version=snapshot_version,
            )
            return dict(row) if row else {"consumer_name": consumer_name, "snapshot_version": snapshot_version}
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    def list_bindings(self, consumer_name: str | None = None) -> list[dict[str, Any]]:
        """바인딩 목록 조회"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        try:
            if consumer_name:
                cur.execute(
                    "SELECT * FROM semantic_runtime_bindings WHERE consumer_name = %s ORDER BY updated_at DESC",
                    (consumer_name,),
                )
            else:
                cur.execute("SELECT * FROM semantic_runtime_bindings ORDER BY updated_at DESC LIMIT 100")
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    # ── 스냅샷 임대 ──

    def acquire_lease(
        self,
        request_id: str,
        consumer_name: str,
        snapshot_version: str,
        ttl_minutes: int = 30,
    ) -> dict[str, Any]:
        """스냅샷 임대를 획득한다 — 요청 단위 낙관적 잠금"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        now = _now_dt()
        expires = now + timedelta(minutes=ttl_minutes)
        lease_id = _uuid()
        try:
            cur.execute("""
                INSERT INTO semantic_snapshot_leases (
                    id, request_id, consumer_name, snapshot_version,
                    acquired_at, expires_at, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (request_id, consumer_name)
                DO UPDATE SET
                    snapshot_version = EXCLUDED.snapshot_version,
                    acquired_at = EXCLUDED.acquired_at,
                    expires_at = EXCLUDED.expires_at,
                    status = EXCLUDED.status,
                    released_at = NULL
                RETURNING *
            """, (
                lease_id, request_id, consumer_name,
                snapshot_version, now, expires, LEASE_ACTIVE,
            ))
            row = cur.fetchone()
            conn.commit()

            logger.info(
                "semantic_lease_acquired",
                request_id=request_id,
                consumer_name=consumer_name,
                snapshot_version=snapshot_version,
                expires_at=expires.isoformat(),
            )
            return dict(row) if row else {
                "request_id": request_id,
                "consumer_name": consumer_name,
                "snapshot_version": snapshot_version,
                "status": LEASE_ACTIVE,
                "expires_at": expires.isoformat(),
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    def release_lease(self, request_id: str, consumer_name: str) -> None:
        """스냅샷 임대를 해제한다"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor()
        now = _now_dt()
        try:
            cur.execute("""
                UPDATE semantic_snapshot_leases
                SET status = %s, released_at = %s
                WHERE request_id = %s AND consumer_name = %s AND status = %s
            """, (LEASE_RELEASED, now, request_id, consumer_name, LEASE_ACTIVE))
            conn.commit()
            logger.info("semantic_lease_released", request_id=request_id, consumer_name=consumer_name)
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    # ── 스냅샷 비교 ──

    def compare_snapshots(
        self, base_version: str, target_version: str
    ) -> dict[str, Any]:
        """두 스냅샷의 아티팩트를 비교하여 변경 목록을 반환한다.

        Args:
            base_version: 기준 스냅샷 버전 (이전)
            target_version: 대상 스냅샷 버전 (이후)

        Returns:
            {"base_version": ..., "target_version": ..., "changes": [...], "summary": {...}}
        """
        self.ensure_schema()

        # 두 스냅샷의 아티팩트를 각각 조회
        base_snap = self.get_snapshot(base_version)
        if not base_snap:
            raise KeyError(f"base_version '{base_version}'를 찾을 수 없습니다")

        target_snap = self.get_snapshot(target_version)
        if not target_snap:
            raise KeyError(f"target_version '{target_version}'를 찾을 수 없습니다")

        # 아티팩트를 {artifact_type: artifact_json} 딕셔너리로 변환
        def _artifacts_to_dict(snap: dict) -> dict[str, dict]:
            result: dict[str, dict] = {}
            for art in snap.get("artifacts", []):
                art_type = art.get("artifact_type", "")
                art_json = art.get("artifact_json", {})
                # DB에서 문자열로 저장된 경우 파싱
                if isinstance(art_json, str):
                    art_json = json.loads(art_json)
                result[art_type] = art_json
            return result

        base_arts = _artifacts_to_dict(base_snap)
        target_arts = _artifacts_to_dict(target_snap)

        # 변경 목록 계산
        changes = _compute_snapshot_changes(base_arts, target_arts)

        # 요약 통계 — 추가/변경/삭제 건수
        summary = {"added": 0, "changed": 0, "deleted": 0}
        for c in changes:
            if c["type"] == "Add":
                summary["added"] += 1
            elif c["type"] == "Change":
                summary["changed"] += 1
            elif c["type"] == "Delete":
                summary["deleted"] += 1

        return {
            "base_version": base_version,
            "target_version": target_version,
            "changes": changes,
            "summary": summary,
            "content_hash_match": base_snap.get("content_hash") == target_snap.get("content_hash"),
        }
