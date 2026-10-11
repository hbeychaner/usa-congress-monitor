from __future__ import annotations

import time

import pytest
from redis import Redis
from redis.exceptions import RedisError

from cdm.utils.rate_limiter import SharedTokenBucket


@pytest.fixture
def redis_client() -> Redis:
    client = Redis.from_url("redis://localhost:6379/15")
    try:
        client.ping()
    except RedisError:
        pytest.skip("Redis is not available")
    client.delete("test:rate")
    return client


def test_two_buckets_share_one_budget(redis_client: Redis) -> None:
    first = SharedTokenBucket(redis_client, "test:rate", rate_per_hour=3600 * 5)
    second = SharedTokenBucket(redis_client, "test:rate", rate_per_hour=3600 * 5)
    start = time.monotonic()
    for _ in range(10):
        first.acquire()
        second.acquire()
    # 20 acquires at 5/s with a 5-token burst take about 3s only if the pool is shared.
    assert time.monotonic() - start > 2
    redis_client.delete("test:rate")
