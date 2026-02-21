from __future__ import annotations

import os


def _csv_list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values


def _sanitize_origins(origins: list[str]) -> list[str]:
    return [origin for origin in origins if origin != "*"]


class Settings:
    def __init__(self) -> None:
        def _enabled(name: str, default: str = "0") -> bool:
            return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}

        self.mindsdb_url = os.getenv("MINDSDB_URL", "http://localhost:47334").rstrip("/")
        self.mindsdb_timeout_seconds = float(os.getenv("MINDSDB_TIMEOUT", "15"))
        self.mindsdb_user = os.getenv("MINDSDB_USER", "")
        self.mindsdb_password = os.getenv("MINDSDB_PASSWORD", "")
        self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", "weaver-dev-secret-change-me")
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_issuer = os.getenv("JWT_ISSUER", "")
        self.jwt_audience = os.getenv("JWT_AUDIENCE", "")
        self.external_mode = _enabled("WEAVER_EXTERNAL_MODE")
        self.metadata_external_mode = _enabled("WEAVER_METADATA_EXTERNAL_MODE")
        self.metadata_pg_mode = _enabled("WEAVER_METADATA_PG_MODE")
        self.postgres_dsn = os.getenv("POSTGRES_DSN", "")
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        self.request_guard_redis_mode = _enabled("WEAVER_REQUEST_GUARD_REDIS_MODE")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.request_guard_idempotency_ttl_seconds = int(os.getenv("WEAVER_REQUEST_GUARD_IDEMPOTENCY_TTL_SECONDS", "600"))
        self.weaver_cors_allowed_origins = _sanitize_origins(
            _csv_list("WEAVER_CORS_ALLOWED_ORIGINS", "https://app.axiom.kr,https://canvas.axiom.kr")
        )
        self.weaver_cors_allowed_methods = _csv_list("WEAVER_CORS_ALLOWED_METHODS", "GET,POST,PUT,DELETE,OPTIONS")
        self.weaver_cors_allowed_headers = _csv_list(
            "WEAVER_CORS_ALLOWED_HEADERS",
            "Authorization,Content-Type,X-Request-Id,Idempotency-Key",
        )


settings = Settings()
