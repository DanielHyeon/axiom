import asyncio

import httpx
import pytest

from app.services.mindsdb_client import MindsDBClient, MindsDBUnavailableError
from app.services.resilience import CircuitBreakerOpenError, SimpleCircuitBreaker, with_retry


class _FakeResponse:
    def __init__(self, status_code: int, payload: object, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):  # type: ignore[no-untyped-def]
        return self._payload


class _SequenceAsyncClient:
    queue: list[object] = []
    post_calls = 0
    get_calls = 0
    ctor_kwargs: list[dict[str, object]] = []

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        type(self).ctor_kwargs.append(dict(kwargs))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    @classmethod
    def reset(cls, items: list[object]) -> None:
        cls.queue = list(items)
        cls.post_calls = 0
        cls.get_calls = 0
        cls.ctor_kwargs = []

    @classmethod
    def _next(cls) -> object:
        if not cls.queue:
            raise AssertionError("no queued fake response")
        return cls.queue.pop(0)

    async def post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        type(self).post_calls += 1
        item = type(self)._next()
        if isinstance(item, Exception):
            raise item
        return item

    async def get(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        type(self).get_calls += 1
        item = type(self)._next()
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def _restore_mindsdb_auth_settings() -> None:
    from app.core.config import settings

    old_user = settings.mindsdb_user
    old_password = settings.mindsdb_password
    try:
        yield
    finally:
        settings.mindsdb_user = old_user
        settings.mindsdb_password = old_password


@pytest.mark.asyncio
async def test_with_retry_retries_and_returns_success() -> None:
    attempts = {"n": 0}

    async def _flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    result = await with_retry(_flaky, retries=3, base_delay_seconds=0.0)
    assert result == "ok"
    assert attempts["n"] == 3


@pytest.mark.asyncio
async def test_with_retry_raises_last_exception() -> None:
    async def _always_fail() -> None:
        raise ValueError("final")

    with pytest.raises(ValueError, match="final"):
        await with_retry(_always_fail, retries=2, base_delay_seconds=0.0)


@pytest.mark.asyncio
async def test_circuit_breaker_opens_and_resets_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    now = {"t": 100.0}
    monkeypatch.setattr("app.services.resilience.time.time", lambda: now["t"])

    breaker = SimpleCircuitBreaker(failure_threshold=3, reset_timeout_seconds=5.0)
    breaker.on_failure()
    breaker.on_failure()
    breaker.preflight()

    breaker.on_failure()
    with pytest.raises(CircuitBreakerOpenError):
        breaker.preflight()

    now["t"] = 106.0
    breaker.preflight()
    assert breaker.failure_count == 0
    assert breaker.opened_at is None


@pytest.mark.asyncio
async def test_mindsdb_client_transient_http_error_recovers_with_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    _SequenceAsyncClient.reset(
        [
            httpx.ConnectError("network glitch"),
            _FakeResponse(200, {"data": [{"name": "analytics"}]}),
        ]
    )
    monkeypatch.setattr("app.services.mindsdb_client.httpx.AsyncClient", _SequenceAsyncClient)

    client = MindsDBClient()
    names = await client.show_databases()

    assert names == ["analytics"]
    assert _SequenceAsyncClient.post_calls == 2
    assert client._breaker.failure_count == 0
    assert client._breaker.opened_at is None


@pytest.mark.asyncio
async def test_mindsdb_client_opens_breaker_after_repeated_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    _SequenceAsyncClient.reset(
        [
            _FakeResponse(503, {"error": "upstream"}, text="upstream failure"),
            _FakeResponse(503, {"error": "upstream"}, text="upstream failure"),
            _FakeResponse(503, {"error": "upstream"}, text="upstream failure"),
        ]
    )
    monkeypatch.setattr("app.services.mindsdb_client.httpx.AsyncClient", _SequenceAsyncClient)

    client = MindsDBClient()

    for _ in range(3):
        with pytest.raises(MindsDBUnavailableError):
            await client.show_databases()

    assert _SequenceAsyncClient.post_calls == 3
    assert client._breaker.opened_at is not None

    with pytest.raises(MindsDBUnavailableError, match="circuit breaker is open"):
        await client.show_databases()

    # Open breaker should fail fast before making another transport call.
    assert _SequenceAsyncClient.post_calls == 3


@pytest.mark.asyncio
async def test_mindsdb_client_applies_basic_auth_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    settings.mindsdb_user = "api-user"
    settings.mindsdb_password = "api-pass"
    _SequenceAsyncClient.reset([_FakeResponse(200, {"status": "ok"})])
    monkeypatch.setattr("app.services.mindsdb_client.httpx.AsyncClient", _SequenceAsyncClient)

    client = MindsDBClient()
    health = await client.health_check()

    assert health["status"] == "ok"
    assert _SequenceAsyncClient.get_calls == 1
    assert _SequenceAsyncClient.ctor_kwargs
    assert _SequenceAsyncClient.ctor_kwargs[0].get("auth") == ("api-user", "api-pass")
