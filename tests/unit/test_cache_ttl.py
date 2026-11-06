import time
from datetime import datetime, timedelta, timezone

from app.broker.cache.broker_cache import BrokerCache


def test_cache_ttl_storage_and_immediate_hit():
    """Verify storing and retrieving unexpired items."""
    cache = BrokerCache()
    cache.set("key1", "value1", ttl_seconds=5)

    assert cache.get("key1") == "value1"


def test_cache_ttl_lazy_expiration():
    """Verify that expired items are evicted on read."""
    cache = BrokerCache()
    # Expire artificially
    cache.set("short_lived", {"foo": "bar"}, ttl_seconds=1)
    # Manually backdate expiry
    entry = cache._store["short_lived"]
    entry.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    # Read should detect expiration, delete key, and return None
    assert cache.get("short_lived") is None
    assert "short_lived" not in cache._store


def test_cache_purge_expired():
    """Verify active sweeper removes all expired entries."""
    cache = BrokerCache()
    cache.set("active", "still_good", ttl_seconds=100)
    cache.set("expired1", "dead", ttl_seconds=1)
    cache.set("expired2", "dead", ttl_seconds=1)

    # Backdate expired entries
    now = datetime.now(timezone.utc)
    cache._store["expired1"].expires_at = now - timedelta(seconds=5)
    cache._store["expired2"].expires_at = now - timedelta(seconds=5)

    purged = cache.purge_expired()
    assert purged == 2
    assert cache.get("active") == "still_good"
    assert cache.get("expired1") is None
    assert cache.get("expired2") is None


def test_cache_partition_helpers():
    """Verify capabilities and session_meta partition methods."""
    cache = BrokerCache()
    caps = {"supported_exchanges": ["NSE", "BSE"]}
    cache.set_capabilities(caps)
    assert cache.get_capabilities() == caps

    meta = {"ucc": "TRADER1", "broker": "KOTAK_NEO"}
    cache.set_session_meta(meta)
    assert cache.get_session_meta() == meta

    cache.clear_session_meta()
    assert cache.get_session_meta() == {}
