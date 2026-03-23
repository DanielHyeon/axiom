"""G08: Redis 어댑터 — experimental 등급.

Redis 키 패턴을 테이블로 매핑, SCAN 기반 키 탐색 + 타입별 스키마 추론.

connection 파라미터:
- url: Redis 연결 URL (예: redis://localhost:6379)
- db: 데이터베이스 번호 (기본: 0)
- password: Redis 비밀번호 (선택)
- key_patterns: 탐색 키 패턴 목록 (선택, 예: ["user:*", "order:*"])
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.models.capability import (
    ConnectorCapability, ConnectorManifest, CredentialMode, SupportTier, register_manifest,
)
from app.services.adapters.base import AdapterFactory, ConnectionTestResult, DatabaseAdapter

logger = logging.getLogger("axiom.weaver.adapters.redis")

try:
    import redis.asyncio as aioredis  # type: ignore
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

# 키 탐색 최대 수
_MAX_SCAN_KEYS = 500
# 패턴별 샘플 키 수
_SAMPLE_PER_PATTERN = 20


class RedisAdapter(DatabaseAdapter):
    """Redis 어댑터 — 키 패턴 기반 메타데이터 탐색.

    키 패턴을 "테이블"로, Redis 데이터 타입별 구조를 "컬럼"으로 매핑한다.
    예: user:* 패턴 → "user" 테이블, hash 필드 → 컬럼
    """

    engine = "redis"

    def _validate(self) -> None:
        if not HAS_REDIS:
            raise ImportError("pip install redis[hiredis]")

    async def _get_client(self) -> Any:
        """aioredis 클라이언트 생성"""
        url = self.connection.get("url", "redis://localhost:6379")
        db = int(self.connection.get("db", 0))
        password = self.connection.get("password", "")
        kwargs: dict[str, Any] = {"db": db, "decode_responses": True}
        if password:
            kwargs["password"] = password
        return aioredis.from_url(url, **kwargs)

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        try:
            client = await self._get_client()
            try:
                await client.ping()
            finally:
                await client.aclose()
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        """Redis DB 번호 = 스키마"""
        db = self.connection.get("db", 0)
        return [f"db{db}"]

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        """키 패턴 → 테이블 매핑.

        전략:
        1. key_patterns 지정 시 해당 패턴으로 SCAN
        2. 미지정 시 SCAN으로 자동 키 패턴 발견 (접두사 그룹핑)
        3. 각 패턴의 샘플 키에서 타입별 스키마 추론
        """
        self._validate()
        client = await self._get_client()
        try:
            patterns = self._get_patterns()

            if not patterns:
                # 자동 패턴 발견: SCAN으로 키를 수집하고 접두사로 그룹핑
                patterns = await self._discover_patterns(client)

            tables = []
            for pattern in patterns:
                table_name = pattern.replace("*", "").rstrip(":").replace(":", "_") or "root"
                columns = await self._infer_pattern_schema(client, pattern)
                entry: dict[str, Any] = {
                    "name": table_name,
                    "columns": columns,
                    "source_specific": {"pattern": pattern, "redis_type": "mixed"},
                }
                if include_row_counts:
                    # 패턴 매칭 키 수 (SCAN 카운트)
                    count = 0
                    async for _ in client.scan_iter(match=pattern, count=100):
                        count += 1
                        if count >= 10000:
                            break
                    entry["row_count"] = count
                tables.append(entry)

            return tables
        finally:
            await client.aclose()

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        """Redis는 FK를 지원하지 않음"""
        return []

    # ── 내부 메서드 ── #

    def _get_patterns(self) -> list[str]:
        """connection에서 키 패턴 목록 추출"""
        patterns = self.connection.get("key_patterns", [])
        if isinstance(patterns, str):
            import json
            try:
                patterns = json.loads(patterns)
            except (ValueError, TypeError):
                patterns = [patterns]
        return list(patterns)

    async def _discover_patterns(self, client: Any) -> list[str]:
        """SCAN으로 키를 수집하고 접두사 기반 패턴 자동 발견.

        예: user:123, user:456 → user:*
            order:2024:001 → order:*

        M3: 타임아웃 + 키 수 제한으로 프로덕션 Redis 부하 방지.
        """
        prefixes: dict[str, int] = {}
        count = 0
        deadline = time.monotonic() + 5.0  # M3: 5초 타임아웃

        async for key in client.scan_iter(count=50):
            count += 1
            if count > _MAX_SCAN_KEYS or time.monotonic() > deadline:
                break

            # 콜론 구분자로 접두사 추출
            if ":" in key:
                prefix = key.split(":")[0]
                prefixes[prefix] = prefixes.get(prefix, 0) + 1
            else:
                prefixes[key] = prefixes.get(key, 0) + 1

        # 2개 이상의 키가 있는 접두사만 패턴으로
        patterns = []
        for prefix, cnt in sorted(prefixes.items(), key=lambda x: -x[1]):
            if cnt >= 2:
                patterns.append(f"{prefix}:*")
            else:
                patterns.append(prefix)

        return patterns[:50]  # 최대 50개 패턴

    async def _infer_pattern_schema(self, client: Any, pattern: str) -> list[dict]:
        """키 패턴에서 샘플 키의 타입별 스키마 추론.

        Redis 타입별 매핑:
        - string → value (TEXT)
        - hash → 필드 → 컬럼
        - list → items (ARRAY)
        - set → members (ARRAY)
        - zset → member + score 컬럼
        """
        try:
            keys = []
            async for key in client.scan_iter(match=pattern, count=100):
                keys.append(key)
                if len(keys) >= _SAMPLE_PER_PATTERN:
                    break

            if not keys:
                return [{"name": "key", "type": "TEXT", "nullable": False}]

            # 첫 번째 키의 타입 확인
            first_key = keys[0]
            key_type = await client.type(first_key)

            if key_type == "hash":
                return await self._schema_from_hash(client, keys)
            elif key_type == "string":
                return [
                    {"name": "key", "type": "TEXT", "nullable": False},
                    {"name": "value", "type": "TEXT", "nullable": True},
                ]
            elif key_type == "list":
                return [
                    {"name": "key", "type": "TEXT", "nullable": False},
                    {"name": "index", "type": "INTEGER", "nullable": False},
                    {"name": "value", "type": "TEXT", "nullable": True},
                ]
            elif key_type == "set":
                return [
                    {"name": "key", "type": "TEXT", "nullable": False},
                    {"name": "member", "type": "TEXT", "nullable": False},
                ]
            elif key_type == "zset":
                return [
                    {"name": "key", "type": "TEXT", "nullable": False},
                    {"name": "member", "type": "TEXT", "nullable": False},
                    {"name": "score", "type": "DECIMAL", "nullable": False},
                ]
            else:
                return [{"name": "key", "type": "TEXT", "nullable": False}]

        except Exception as e:
            logger.warning("Redis 스키마 추론 실패: %s — %s", pattern, e)
            return [{"name": "key", "type": "TEXT", "nullable": False}]

    async def _schema_from_hash(self, client: Any, keys: list[str]) -> list[dict]:
        """Hash 타입 키에서 필드 → 컬럼 매핑 (여러 키의 필드 병합)"""
        all_fields: dict[str, str] = {}

        for key in keys:
            try:
                fields = await client.hgetall(key)
                for fname, fvalue in fields.items():
                    if fname not in all_fields:
                        # 값으로 타입 추론
                        all_fields[fname] = self._infer_hash_field_type(fvalue)
            except Exception:
                continue

        columns = [{"name": "key", "type": "TEXT", "nullable": False}]
        for fname in sorted(all_fields):
            columns.append({
                "name": fname,
                "type": all_fields[fname],
                "nullable": True,
            })

        return columns if len(columns) > 1 else [{"name": "key", "type": "TEXT", "nullable": False}]

    def _infer_hash_field_type(self, value: str) -> str:
        """Redis hash 필드 값에서 타입 추론 (모두 문자열로 저장됨)"""
        if not value:
            return "TEXT"
        # 정수 확인
        try:
            int(value)
            return "INTEGER"
        except ValueError:
            pass
        # 실수 확인
        try:
            float(value)
            return "DECIMAL"
        except ValueError:
            pass
        # 불리언 확인
        if value.lower() in ("true", "false"):
            return "BOOLEAN"
        return "TEXT"


def _register():
    AdapterFactory.register("redis", RedisAdapter)
    register_manifest(ConnectorManifest(
        engine="redis", display_name="Redis",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.SAMPLE_PREVIEW,
        ],
        credential_modes=[CredentialMode.INTERNAL],
        support_tier=SupportTier.EXPERIMENTAL, version="0.1.0",
        description="Redis — SCAN 기반 키 패턴 탐색 + 타입별 스키마 추론",
    ))

_register()
