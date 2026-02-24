"""Tests for SynapseMetadataClient (DDD-P2-05)."""
import pytest

from app.services.synapse_metadata_client import (
    SynapseMetadataClient,
    SynapseMetadataClientError,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(self.status_code),
            )


class _FakeAsyncClient:
    """Simulates httpx.AsyncClient for testing."""

    def __init__(self, responses: list[_FakeResponse] | None = None):
        self._responses = list(responses or [])
        self._call_idx = 0
        self.calls: list[tuple[str, str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def _next(self, method: str, url: str, **kwargs) -> _FakeResponse:
        self.calls.append((method, url, kwargs))
        if self._call_idx < len(self._responses):
            resp = self._responses[self._call_idx]
            self._call_idx += 1
            return resp
        return _FakeResponse(200, {"success": True})

    async def get(self, url, **kw):
        return self._next("GET", url, **kw)

    async def post(self, url, **kw):
        return self._next("POST", url, **kw)

    async def delete(self, url, **kw):
        return self._next("DELETE", url, **kw)


# ──── Snapshot tests ──── #


@pytest.mark.asyncio
async def test_save_snapshot(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"success": True})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    await client.save_snapshot({"id": "s1"}, tenant_id="t1")
    assert fake.calls[0][0] == "POST"
    assert fake.calls[0][1] == "/snapshots"


@pytest.mark.asyncio
async def test_list_snapshots(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"data": [{"id": "s1"}]})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.list_snapshots("c1", "ds1", tenant_id="t1")
    assert result == [{"id": "s1"}]


@pytest.mark.asyncio
async def test_get_snapshot_found(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"data": {"id": "s1"}})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.get_snapshot("c1", "ds1", "s1")
    assert result == {"id": "s1"}


@pytest.mark.asyncio
async def test_get_snapshot_not_found(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(404)])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.get_snapshot("c1", "ds1", "s1")
    assert result is None


@pytest.mark.asyncio
async def test_delete_snapshot(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"deleted": True})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.delete_snapshot("c1", "ds1", "s1")
    assert result is True


# ──── Glossary tests ──── #


@pytest.mark.asyncio
async def test_save_glossary_term(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200)])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    await client.save_glossary_term({"id": "g1"})
    assert fake.calls[0][1] == "/glossary"


@pytest.mark.asyncio
async def test_list_glossary_terms(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"data": [{"id": "g1"}]})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.list_glossary_terms()
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_glossary_term_found(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"data": {"id": "g1"}})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.get_glossary_term("g1")
    assert result == {"id": "g1"}


@pytest.mark.asyncio
async def test_get_glossary_term_not_found(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(404)])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.get_glossary_term("g1")
    assert result is None


@pytest.mark.asyncio
async def test_delete_glossary_term(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"deleted": True})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.delete_glossary_term("g1")
    assert result is True


@pytest.mark.asyncio
async def test_search_glossary_terms(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"data": [{"id": "g1"}]})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.search_glossary_terms("test")
    assert len(result) == 1


# ──── Entity Tags tests ──── #


@pytest.mark.asyncio
async def test_add_entity_tag(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"tags": ["pii", "sensitive"]})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.add_entity_tag("key1", "table", {}, "pii")
    assert result == ["pii", "sensitive"]


@pytest.mark.asyncio
async def test_list_entity_tags(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"tags": ["pii"]})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.list_entity_tags("key1")
    assert result == ["pii"]


@pytest.mark.asyncio
async def test_remove_entity_tag(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"removed": True})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.remove_entity_tag("key1", "pii")
    assert result is True


@pytest.mark.asyncio
async def test_entities_by_tag(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"data": [{"key": "k1"}]})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.entities_by_tag("pii")
    assert len(result) == 1


# ──── Datasource tests ──── #


@pytest.mark.asyncio
async def test_upsert_datasource(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200)])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    await client.upsert_datasource("ds1", "postgresql")
    assert fake.calls[0][0] == "POST"


@pytest.mark.asyncio
async def test_delete_datasource(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200)])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    await client.delete_datasource("ds1")
    assert fake.calls[0][0] == "DELETE"


@pytest.mark.asyncio
async def test_save_extracted_catalog(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"data": {"nodes": 5, "edges": 3}})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.save_extracted_catalog("t1", "ds1", {"public": {}})
    assert result == {"nodes": 5, "edges": 3}


# ──── Stats test ──── #


@pytest.mark.asyncio
async def test_stats(monkeypatch):
    client = SynapseMetadataClient()
    fake = _FakeAsyncClient([_FakeResponse(200, {"data": {"datasources": 2, "glossary_terms": 5, "snapshots": 3}})])
    monkeypatch.setattr(client, "_session", lambda tid="": _ctx(fake))
    result = await client.stats()
    assert result == {"datasources": 2, "glossary_terms": 5, "snapshots": 3}


# ──── Error wrapping test ──── #


@pytest.mark.asyncio
async def test_error_wrapping_via_session(monkeypatch):
    """Verify _session wraps httpx errors into SynapseMetadataClientError."""
    import httpx as _httpx

    class _ErrorClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            pass
        async def get(self, *a, **kw):
            raise _httpx.ConnectError("connection refused")

    monkeypatch.setattr(
        "app.services.synapse_metadata_client.httpx.AsyncClient",
        lambda **kw: _ErrorClient(),
    )
    client = SynapseMetadataClient()
    with pytest.raises(SynapseMetadataClientError, match="connection refused"):
        await client.list_glossary_terms()


@pytest.mark.asyncio
async def test_health_check_error_wrapping(monkeypatch):
    import httpx as _httpx

    class _FailClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            pass
        async def get(self, *a, **kw):
            raise _httpx.ConnectError("connection refused")

    monkeypatch.setattr(
        "app.services.synapse_metadata_client.httpx.AsyncClient",
        lambda **kw: _FailClient(),
    )
    client = SynapseMetadataClient()
    with pytest.raises(SynapseMetadataClientError, match="connection refused"):
        await client.health_check()


# ──── Helper ──── #


from contextlib import asynccontextmanager


@asynccontextmanager
async def _ctx(fake_client):
    """Helper to wrap _FakeAsyncClient as an async context manager."""
    try:
        yield fake_client
    except Exception:
        raise
