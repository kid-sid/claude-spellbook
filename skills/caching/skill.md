---
name: caching
description: Caching patterns covering Redis data structures, cache-aside/write-through/write-behind strategies, TTL design, cache stampede prevention, CDN caching, HTTP cache headers, invalidation strategies, and distributed cache pitfalls for Python, TypeScript, and Go.
---

# Caching Patterns

Strategies and implementation patterns for application-level, distributed, and HTTP caching.

## When to Activate

- Adding Redis or Memcached to reduce database load or API latency
- Designing TTL values and cache invalidation strategies
- Preventing cache stampede on high-traffic keys
- Configuring HTTP `Cache-Control` and CDN caching rules
- Choosing between cache-aside, write-through, or write-behind
- Debugging stale data, cache poisoning, or thundering herd problems
- Sizing a cache or deciding what to cache vs. not cache

## Strategy Selection

| Strategy | How | Best For |
|---|---|---|
| Cache-aside (lazy) | App checks cache first; on miss, loads from DB, populates cache | General-purpose read caching |
| Write-through | Write to cache and DB simultaneously | Data that's read immediately after write |
| Write-behind (write-back) | Write to cache; async flush to DB | High write throughput, tolerance for small loss window |
| Read-through | Cache fetches from DB on miss (cache manages itself) | Managed caches (ElastiCache DAX, Momento) |
| Refresh-ahead | Proactively refresh before expiry | Predictable access patterns, zero-miss latency required |

## Cache-Aside (Most Common)

```python
# Python — cache-aside with Redis
import redis, json, hashlib
from typing import Callable, TypeVar

T = TypeVar("T")
r = redis.Redis(host="redis", port=6379, decode_responses=True)

def get_or_set(key: str, loader: Callable[[], T], ttl: int = 300) -> T:
    cached = r.get(key)
    if cached is not None:
        return json.loads(cached)

    value = loader()
    r.setex(key, ttl, json.dumps(value, default=str))
    return value

# Usage
user = get_or_set(f"user:{user_id}", lambda: db.query(User).get(user_id), ttl=600)
```

```typescript
// TypeScript — cache-aside
import { createClient } from "redis";

const redis = createClient({ url: "redis://redis:6379" });

async function getOrSet<T>(
  key: string,
  loader: () => Promise<T>,
  ttlSeconds = 300,
): Promise<T> {
  const cached = await redis.get(key);
  if (cached) return JSON.parse(cached) as T;

  const value = await loader();
  await redis.setEx(key, ttlSeconds, JSON.stringify(value));
  return value;
}
```

```go
// Go — cache-aside
func (c *Cache) GetOrSet(ctx context.Context, key string, loader func() (any, error), ttl time.Duration) (any, error) {
    val, err := c.redis.Get(ctx, key).Result()
    if err == nil {
        var result any
        json.Unmarshal([]byte(val), &result)
        return result, nil
    }
    if !errors.Is(err, redis.Nil) {
        return nil, err
    }

    data, err := loader()
    if err != nil {
        return nil, err
    }
    b, _ := json.Marshal(data)
    c.redis.SetEx(ctx, key, string(b), ttl)
    return data, nil
}
```

## Cache Key Design

```
# Pattern: <service>:<entity>:<id>[:<variant>]
user:profile:123
user:orders:123:active
product:detail:sku-456
search:results:<md5(query+filters)>

# BAD: too broad — invalidation nukes unrelated data
cache_key = "users"

# BAD: too granular — misses sharing opportunity
cache_key = f"user_orders_by_{user_id}_status_{status}_page_{page}"

# GOOD: namespace + entity + discriminator
cache_key = f"user:{user_id}:orders:{status}"   # paginate in app, not in key
```

## TTL Design

| Data Type | TTL Range | Reasoning |
|---|---|---|
| User session | 15–60 min (sliding) | Balance UX vs. stale auth |
| User profile | 5–15 min | Infrequent changes, high read volume |
| Product catalog | 1–24 hr | Changes only on explicit update |
| Search results | 1–5 min | Acceptable staleness for non-personalized |
| Rate limit counters | Match the window (60s, 3600s) | Must expire with the window |
| One-time tokens | Exact validity period | No grace period |
| Computed aggregates | 1–10 min | Trade accuracy for throughput |

```python
# Sliding TTL for sessions — reset on every access
def get_session(session_id: str) -> dict | None:
    key = f"session:{session_id}"
    data = r.get(key)
    if data:
        r.expire(key, 1800)  # extend on access
        return json.loads(data)
    return None
```

## Cache Stampede Prevention

When a popular key expires, many requests hit the DB simultaneously.

### Probabilistic Early Recomputation (XFetch)

```python
import math, random, time

def fetch_with_xfetch(key: str, loader: Callable[[], T], ttl: int, beta: float = 1.0) -> T:
    cached_raw = r.get(key)
    if cached_raw:
        entry = json.loads(cached_raw)
        delta = entry["compute_time"]
        remaining_ttl = r.ttl(key)
        # probabilistically recompute before expiry
        if remaining_ttl - beta * delta * math.log(random.random()) < 0:
            cached_raw = None  # trigger recompute
        else:
            return entry["value"]

    start = time.monotonic()
    value = loader()
    compute_time = time.monotonic() - start
    r.setex(key, ttl, json.dumps({"value": value, "compute_time": compute_time}, default=str))
    return value
```

### Mutex Lock (Simpler)

```python
import time

def get_with_lock(key: str, loader: Callable[[], T], ttl: int) -> T:
    cached = r.get(key)
    if cached:
        return json.loads(cached)

    lock_key = f"{key}:lock"
    acquired = r.set(lock_key, "1", nx=True, ex=10)  # 10s lock timeout

    if acquired:
        try:
            value = loader()
            r.setex(key, ttl, json.dumps(value, default=str))
            return value
        finally:
            r.delete(lock_key)
    else:
        # Wait and retry — another worker is computing
        time.sleep(0.1)
        return get_with_lock(key, loader, ttl)
```

## Redis Data Structures

```python
# String — simple values, counters
r.set("config:feature_x", "enabled")
r.incr("counter:api_calls:2025-06-01")

# Hash — object fields (avoids full serialization for partial updates)
r.hset("user:123", mapping={"name": "Alice", "plan": "pro"})
r.hget("user:123", "plan")
r.hgetall("user:123")

# Set — membership, deduplication
r.sadd("online_users", "user:123", "user:456")
r.sismember("online_users", "user:123")

# Sorted Set — leaderboards, rate limiting with sliding window
r.zadd("leaderboard", {"user:123": 1500, "user:456": 2000})
r.zrevrange("leaderboard", 0, 9, withscores=True)  # top 10

# List — queues, recent activity
r.lpush("recent:user:123", "order:789")
r.ltrim("recent:user:123", 0, 49)  # keep last 50

# Stream — event log with consumer groups (lightweight Kafka alternative)
r.xadd("events:orders", {"event_type": "placed", "order_id": "abc"})
```

## Invalidation Strategies

```python
# 1. TTL expiry — simplest, eventual consistency
r.setex(key, 300, value)

# 2. Explicit delete on write — strong consistency
def update_user(user_id: str, data: dict):
    db.update(User, user_id, data)
    r.delete(f"user:profile:{user_id}")  # invalidate immediately
    r.delete(f"user:orders:{user_id}:*")  # careful: KEYS is O(N), use SCAN

# 3. Tag-based invalidation — invalidate groups of keys
def set_with_tag(key: str, value: any, tag: str, ttl: int):
    r.setex(key, ttl, json.dumps(value))
    r.sadd(f"tag:{tag}", key)
    r.expire(f"tag:{tag}", ttl + 60)

def invalidate_tag(tag: str):
    keys = r.smembers(f"tag:{tag}")
    if keys:
        r.delete(*keys)
    r.delete(f"tag:{tag}")

# 4. Cache-aside with versioning — no explicit invalidation needed
def versioned_key(entity: str, entity_id: str) -> str:
    version = r.get(f"version:{entity}:{entity_id}") or "0"
    return f"{entity}:{entity_id}:v{version}"

def invalidate(entity: str, entity_id: str):
    r.incr(f"version:{entity}:{entity_id}")  # old keys naturally expire
```

## Rate Limiting with Redis

```python
# Sliding window counter
def is_rate_limited(user_id: str, limit: int = 100, window: int = 60) -> bool:
    key = f"ratelimit:{user_id}"
    now = time.time()
    window_start = now - window

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)  # remove old entries
    pipe.zadd(key, {str(now): now})              # add current request
    pipe.zcard(key)                              # count in window
    pipe.expire(key, window)
    results = pipe.execute()

    return results[2] > limit

# Token bucket (alternative — smoother bursting)
def consume_token(key: str, rate: float, capacity: int) -> bool:
    lua = """
    local tokens = tonumber(redis.call('GET', KEYS[1])) or tonumber(ARGV[2])
    local last = tonumber(redis.call('GET', KEYS[2])) or tonumber(ARGV[3])
    local now = tonumber(ARGV[3])
    local rate = tonumber(ARGV[1])
    local capacity = tonumber(ARGV[2])
    tokens = math.min(capacity, tokens + (now - last) * rate)
    if tokens >= 1 then
        redis.call('SET', KEYS[1], tokens - 1)
        redis.call('SET', KEYS[2], now)
        return 1
    end
    return 0
    """
    # Use redis.eval() with Lua for atomic token bucket
```

## HTTP Caching

### Cache-Control Headers

```
# Static assets — long cache, versioned URLs
Cache-Control: public, max-age=31536000, immutable   # 1 year; URL changes on update

# API responses — CDN-cacheable, short TTL
Cache-Control: public, max-age=60, s-maxage=300      # browser 1min, CDN 5min

# Authenticated API responses — never CDN-cache
Cache-Control: private, max-age=0, must-revalidate

# Never cache
Cache-Control: no-store

# Revalidate with ETag
Cache-Control: no-cache                               # always revalidate; use ETag
ETag: "abc123"

# Vary header — CDN stores separate copies per value
Vary: Accept-Encoding, Accept-Language
```

### ETags and Conditional Requests

```python
from hashlib import md5
from flask import request, jsonify, make_response

@app.get("/api/products/<product_id>")
def get_product(product_id: str):
    product = get_product_from_db(product_id)
    etag = md5(json.dumps(product, sort_keys=True).encode()).hexdigest()

    if request.headers.get("If-None-Match") == etag:
        return "", 304  # Not Modified — no body, saves bandwidth

    response = make_response(jsonify(product))
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=60"
    return response
```

## Distributed Cache Pitfalls

```
# 1. Cache penetration — repeated misses for non-existent keys
Solution: cache null/"not found" with short TTL (30–60s)
r.setex(key, 60, json.dumps(None))

# 2. Cache avalanche — many keys expire simultaneously
Solution: add jitter to TTL
ttl = base_ttl + random.randint(0, base_ttl // 10)

# 3. Hot key — single key receiving disproportionate traffic
Solution: local in-process cache as L1, Redis as L2
from functools import lru_cache
@lru_cache(maxsize=1000)
def get_config(key: str): ...  # millisecond in-process cache

# 4. Large values — serializing/deserializing huge objects
Solution: store field-level with Redis Hash; never cache full result sets > 1MB

# 5. Stale reads after failover
Solution: use Redis Sentinel or Cluster; never rely on single-node without replication
```

> See also: `performance`, `database-design`, `api-design`

## Checklist

- [ ] Cache keys follow `<service>:<entity>:<id>` namespace convention
- [ ] TTL values justified per data type — not a single global default
- [ ] Cache-aside pattern implemented; null results cached with short TTL (prevents cache penetration)
- [ ] TTL jitter applied to prevent cache avalanche on mass expiry
- [ ] High-traffic keys protected against stampede (mutex lock or XFetch)
- [ ] Invalidation strategy defined: TTL only, explicit delete on write, or versioned keys
- [ ] Sensitive data (auth tokens, PII) uses `private` Cache-Control or not cached at all
- [ ] Static assets served with long `max-age` + `immutable` + content-hashed URLs
- [ ] Rate limiters use atomic Redis operations (Lua scripts or pipeline)
- [ ] Redis connection pooling configured; not creating new connection per request
- [ ] Cache hit rate monitored; eviction policy set (`allkeys-lru` or `volatile-lru`)
- [ ] No `KEYS *` in production — use `SCAN` for bulk operations
