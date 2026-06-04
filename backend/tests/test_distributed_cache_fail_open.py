from __future__ import annotations

import pytest

from app.services.shared import distributed_cache


class TimeoutClient:
    def get(self, *_args, **_kwargs):
        raise TimeoutError("Timeout reading from socket")

    def setex(self, *_args, **_kwargs):
        raise TimeoutError("Timeout reading from socket")

    def mget(self, *_args, **_kwargs):
        raise TimeoutError("Timeout reading from socket")


def test_set_text_cache_fail_open_records_error(monkeypatch):
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(distributed_cache, "get_distributed_cache_client", lambda: TimeoutClient())
    monkeypatch.setattr(
        distributed_cache,
        "_record_cache_error",
        lambda operation, reason: events.append((operation, reason)),
    )

    result = distributed_cache.set_text_cache("k", "v", ttl_seconds=5, fail_open=True)

    assert result is False
    assert events == [("set", "timeout")]


def test_get_text_cache_fail_open_returns_none(monkeypatch):
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(distributed_cache, "get_distributed_cache_client", lambda: TimeoutClient())
    monkeypatch.setattr(
        distributed_cache,
        "_record_cache_error",
        lambda operation, reason: events.append((operation, reason)),
    )

    result = distributed_cache.get_text_cache("k", fail_open=True)

    assert result is None
    assert events == [("get", "timeout")]


def test_get_many_json_cache_fail_open_returns_empty(monkeypatch):
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(distributed_cache, "get_distributed_cache_client", lambda: TimeoutClient())
    monkeypatch.setattr(
        distributed_cache,
        "_record_cache_error",
        lambda operation, reason: events.append((operation, reason)),
    )

    result = distributed_cache.get_many_json_cache(["a", "b"], fail_open=True)

    assert result == {}
    assert events == [("mget", "timeout")]


def test_get_text_cache_can_still_raise_when_fail_open_disabled(monkeypatch):
    monkeypatch.setattr(distributed_cache, "get_distributed_cache_client", lambda: TimeoutClient())

    with pytest.raises(TimeoutError):
        distributed_cache.get_text_cache("k", fail_open=False)
