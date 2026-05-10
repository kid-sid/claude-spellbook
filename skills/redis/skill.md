---
name: redis
description: Use when choosing a Redis data structure for a use case, implementing caching or rate limiting, building pub/sub or Streams-based real-time messaging, or writing atomic operations like distributed locks.
---

# Redis Patterns

Redis data structures, caching, pub/sub, and streams for Python async apps.

## When to Activate

- Choosing the right Redis data structure for a use case
- Implementing caching (cache-aside, write-through, TTL eviction)
- Using pub/sub or Redis Streams for real-time messaging / SSE
- Building a job queue with SKIP LOCKED semantics
- Writing atomic operations (counters, rate limits, distributed locks)
- Debugging slow Redis commands or memory bloat

---

## Connection (async redis-py)

```python
import redis.asyncio as redis

# Single connection
client = await redis.from_url("redis://localhost:6379", decode_responses=True)

# Connection pool (recommended for apps)
pool = redis.ConnectionPool.from_url(
    "redis://localhost:6379",
    decode_responses=True,
    max_connections=20,
)
client = redis.Redis(connection_pool=pool)

# Close on shutdown
await client.aclose()
```

`decode_responses=True` returns `str` instead of `bytes` — use it unless you store binary data.

---

## Data Structure Decision Table

| Structure | Use For | Avoid When |
|---|---|---|
| **String** | Single values, JSON blobs, counters, distributed locks | Frequently updating one field of many |
| **Hash** | Objects with multiple fields; partial field reads/writes | >100 fields or deeply nested — use String+JSON instead |
| **List** | FIFO queues, activity feeds, bounded history | Random access by index — use Sorted Set |
| **Set** | Unique membership, tag intersections/unions, "online users" | Need ordering or score — use Sorted Set |
| **Sorted Set** | Leaderboards, priority queues, time-ordered events, rate limiting | Cardinality >10M — memory gets expensive |
| **Stream** | Durable pub/sub, consumer groups, event log | Simple fire-and-forget — use pub/sub |
| **HyperLogLog** | Approx unique count (±0.81% error, capped at 12 KB) | Exact count required |
| **Bitmap** | Per-user boolean flags, daily active user tracking | More than 512 MB of bits |

---

## Data Structures

### Strings — single values, counters, JSON blobs

```python
# Set / get
await client.set("user:123:name", "Alice")
await client.get("user:123:name")            # "Alice"

# With TTL (seconds)
await client.set("session:abc", token, ex=3600)    # expires in 1 hour
await client.setex("session:abc", 3600, token)     # same

# Only set if not exists (NX) — distributed lock primitive
acquired = await client.set("lock:job:42", "worker-1", nx=True, ex=30)

# Atomic counter
await client.incr("page:views")
await client.incrby("page:views", 5)
await client.decr("inventory:product:99")

# Get + set atomically (Lua or GETEX)
await client.getex("session:abc", ex=3600)   # reset TTL on read

# Store JSON
import json
await client.set("user:123", json.dumps(user_dict))
user = json.loads(await client.get("user:123"))
```

### Hashes — objects / partial updates

```python
# Set multiple fields at once
await client.hset("user:123", mapping={
    "name": "Alice",
    "email": "alice@example.com",
    "role": "admin",
})

# Get all fields
user = await client.hgetall("user:123")     # {"name": "Alice", ...}

# Get one field
name = await client.hget("user:123", "name")

# Update one field without overwriting others
await client.hset("user:123", "role", "user")

# Check existence
exists = await client.hexists("user:123", "email")

# Delete a field
await client.hdel("user:123", "temp_token")

# Get field names / values
fields = await client.hkeys("user:123")
values = await client.hvals("user:123")
```

Use hashes for objects with many fields where you update individual fields often. Cheaper than JSON string for partial reads.

### Lists — queues, activity feeds

```python
# Push to right (tail) — enqueue
await client.rpush("queue:emails", "msg-1", "msg-2")

# Pop from left (head) — dequeue FIFO
job = await client.lpop("queue:emails")

# Blocking pop — wait up to 30s for an item
job = await client.blpop("queue:emails", timeout=30)   # returns (key, value)

# Stack (LIFO): rpush + rpop
await client.rpush("stack", "item")
item = await client.rpop("stack")

# Peek without removing
items = await client.lrange("queue:emails", 0, -1)   # all items
recent = await client.lrange("activity:user:1", 0, 9)  # first 10

# Keep list bounded (trim to last 100)
await client.ltrim("activity:user:1", -100, -1)

# Length
length = await client.llen("queue:emails")
```

### Sets — unique membership, tags

```python
await client.sadd("online_users", "user-1", "user-2")
await client.srem("online_users", "user-2")

is_online = await client.sismember("online_users", "user-1")
members = await client.smembers("online_users")
count = await client.scard("online_users")

# Set operations
common = await client.sinter("user:1:friends", "user:2:friends")  # intersection
all_  = await client.sunion("tag:python", "tag:async")             # union
diff  = await client.sdiff("all_users", "banned_users")            # difference
```

### Sorted Sets — leaderboards, priority queues, rate limiting

```python
# Add with score (score determines order)
await client.zadd("leaderboard", {"alice": 1500, "bob": 1200, "carol": 1800})

# Get top 3 (highest score first)
top3 = await client.zrevrange("leaderboard", 0, 2, withscores=True)
# [("carol", 1800.0), ("alice", 1500.0), ("bob", 1200.0)]

# Rank (0-indexed, lowest score = rank 0)
rank = await client.zrevrank("leaderboard", "alice")   # 1 (2nd place)

# Increment score atomically
await client.zincrby("leaderboard", 50, "bob")

# Range by score — get items between two scores
members = await client.zrangebyscore("leaderboard", 1400, 2000)

# Remove
await client.zrem("leaderboard", "bob")
```

---

## TTL and Expiration

```python
# Set TTL on existing key
await client.expire("session:abc", 3600)           # seconds
await client.expireat("session:abc", timestamp)    # unix timestamp
await client.pexpire("key", 500)                   # milliseconds

# Check remaining TTL
ttl = await client.ttl("session:abc")    # seconds remaining, -1 if no TTL, -2 if missing
pttl = await client.pttl("session:abc") # milliseconds

# Remove TTL (make persistent)
await client.persist("key")
```

---

## Pub/Sub

```python
# Publisher
async def publish_event(client, channel: str, data: dict):
    await client.publish(channel, json.dumps(data))

# Subscriber — runs indefinitely
async def subscribe_to_events(client, channel: str):
    async with client.pubsub() as pubsub:
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                yield data

# Pattern subscribe
async with client.pubsub() as pubsub:
    await pubsub.psubscribe("tasks:*")   # matches tasks:created, tasks:done, etc.
    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            process(message["channel"], message["data"])
```

**Limitation:** pub/sub messages are fire-and-forget. Subscribers that miss a message while offline don't receive it. Use Streams for durable delivery.

---

## Redis Streams (durable pub/sub)

Streams persist messages — consumers can read from any position, including past messages.

```python
# Produce — append message to stream
msg_id = await client.xadd(
    "task:updates",
    {"task_id": "t-123", "status": "running", "content": "Processing..."},
    maxlen=10000,     # trim to 10k entries (approximate)
)

# Consume from beginning
messages = await client.xread({"task:updates": "0-0"}, count=100)
# messages: [("task:updates", [(id, {fields...}), ...])]

# Consume only new messages (since last read)
last_id = "0-0"
messages = await client.xread({"task:updates": last_id}, count=10, block=5000)
for stream, entries in messages:
    for msg_id, fields in entries:
        process(fields)
        last_id = msg_id

# Consumer groups — multiple workers compete for messages
await client.xgroup_create("task:updates", "workers", id="0", mkstream=True)

# Worker reads and claims a message
msgs = await client.xreadgroup("workers", "worker-1", {"task:updates": ">"}, count=1)
for stream, entries in msgs:
    for msg_id, fields in entries:
        process(fields)
        await client.xack("task:updates", "workers", msg_id)   # mark done

# Trim old entries
await client.xtrim("task:updates", maxlen=5000, approximate=True)
```

**SSE streaming pattern** (used in Agentex frontend):
```python
# Backend: push deltas to a stream per task
await client.xadd(f"task:{task_id}:stream", {"delta": chunk})

# Frontend SSE endpoint: read stream and forward to browser
async def stream_task(task_id: str):
    last_id = "0-0"
    while True:
        messages = await client.xread({f"task:{task_id}:stream": last_id}, block=5000)
        for _, entries in messages:
            for msg_id, fields in entries:
                yield f"data: {fields['delta']}\n\n"
                last_id = msg_id
```

---

## Caching Patterns

### Cache-aside (lazy loading)

```python
async def get_user(user_id: str) -> User:
    key = f"user:{user_id}"
    cached = await client.get(key)
    if cached:
        return User(**json.loads(cached))

    user = await db.fetch_user(user_id)
    await client.set(key, user.model_dump_json(), ex=300)   # cache 5 min
    return user

async def invalidate_user(user_id: str):
    await client.delete(f"user:{user_id}")
```

### Write-through

```python
async def update_user(user_id: str, data: dict) -> User:
    user = await db.update_user(user_id, data)
    await client.set(f"user:{user_id}", user.model_dump_json(), ex=300)
    return user
```

---

## Atomic Operations

### Distributed lock

```python
import uuid

async def with_lock(client, resource: str, ttl: int = 30):
    lock_key = f"lock:{resource}"
    lock_val = str(uuid.uuid4())

    acquired = await client.set(lock_key, lock_val, nx=True, ex=ttl)
    if not acquired:
        raise RuntimeError(f"Could not acquire lock on {resource}")
    try:
        yield
    finally:
        # Only release if we still own it (Lua script for atomicity)
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        await client.eval(script, 1, lock_key, lock_val)
```

### Rate limiting (sliding window)

```python
async def is_rate_limited(client, user_id: str, limit: int = 100, window: int = 60) -> bool:
    key = f"rate:{user_id}:{int(time.time()) // window}"
    count = await client.incr(key)
    if count == 1:
        await client.expire(key, window)
    return count > limit
```

### Pipeline (batch commands — reduce round trips)

```python
async with client.pipeline(transaction=False) as pipe:
    pipe.hset("user:1", mapping=data)
    pipe.expire("user:1", 3600)
    pipe.zadd("leaderboard", {"user-1": score})
    results = await pipe.execute()   # sent as one network round trip

# Atomic pipeline (MULTI/EXEC)
async with client.pipeline(transaction=True) as pipe:
    await pipe.watch("inventory:42")
    quantity = int(await pipe.get("inventory:42"))
    if quantity < 1:
        raise Exception("Out of stock")
    pipe.multi()
    pipe.decr("inventory:42")
    await pipe.execute()
```

---

## SCAN — Non-Blocking Key Iteration

Never use `KEYS *` in production. Use `SCAN` with a cursor instead:

```python
# Python — iterate all keys matching a pattern without blocking
async def scan_keys(client, pattern: str) -> list[str]:
    keys = []
    cursor = 0
    while True:
        cursor, batch = await client.scan(cursor, match=pattern, count=100)
        keys.extend(batch)
        if cursor == 0:
            break
    return keys

# Scan hash fields
cursor = 0
while True:
    cursor, fields = await client.hscan("user:123", cursor, count=50)
    for field, value in fields.items():
        process(field, value)
    if cursor == 0:
        break

# Scan sorted set members by score range (non-blocking alternative to ZRANGEBYSCORE on huge sets)
cursor = 0
while True:
    cursor, members = await client.zscan("leaderboard", cursor, count=100)
    for member, score in members:
        process(member, score)
    if cursor == 0:
        break
```

---

## Eviction Policies

Set `maxmemory` and `maxmemory-policy` in `redis.conf` or via `CONFIG SET`:

```bash
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

| Policy | Evicts | Use When |
|---|---|---|
| `noeviction` | Nothing — returns error on write | Data must never be lost (primary store) |
| `allkeys-lru` | Least-recently-used key (any key) | General cache — you can't control which keys have TTL |
| `volatile-lru` | LRU among keys with TTL | Mix of persistent + cache keys in one instance |
| `allkeys-lfu` | Least-frequently-used key (any key) | Hotspot skew — some keys accessed far more |
| `volatile-ttl` | Key with shortest remaining TTL | Prefer expiring the soonest-to-expire keys |
| `allkeys-random` | Random key | Uniform access patterns, lowest overhead |

**Production default for caches:** `allkeys-lru`  
**Never use `noeviction` for a cache** — the first write after memory is full raises an error.

```python
# Check current eviction policy
info = await client.config_get("maxmemory-policy")
# {'maxmemory-policy': 'allkeys-lru'}

# Monitor eviction rate
stats = await client.info("stats")
evicted = stats["evicted_keys"]   # total evictions since start
```

---

## TypeScript Patterns (node-redis)

```typescript
import { createClient } from "redis";

const client = createClient({
  url: "redis://localhost:6379",
  socket: { reconnectStrategy: (retries) => Math.min(retries * 50, 2000) },
});
await client.connect();

// String / JSON
await client.set("user:123", JSON.stringify(user), { EX: 300 });
const raw = await client.get("user:123");
const user = raw ? JSON.parse(raw) : null;

// Hash
await client.hSet("user:123", { name: "Alice", role: "admin" });
const data = await client.hGetAll("user:123");  // Record<string, string>

// Sorted set
await client.zAdd("leaderboard", [{ score: 1500, value: "alice" }]);
const top = await client.zRangeWithScores("leaderboard", 0, 9, { REV: true });

// Pipeline
const pipeline = client.multi();
pipeline.set("a", "1");
pipeline.expire("a", 60);
pipeline.incr("counter");
const [, , count] = await pipeline.exec();

// Distributed lock
const acquired = await client.set("lock:job:42", workerId, { NX: true, EX: 30 });
if (!acquired) throw new Error("Lock unavailable");

// Pub/sub (separate subscriber client)
const sub = client.duplicate();
await sub.connect();
await sub.subscribe("events", (message) => {
  const data = JSON.parse(message);
  handle(data);
});
```

---

## Sentinel & Cluster Connections

```python
# Sentinel (high availability — automatic failover)
from redis.sentinel import Sentinel

sentinel = Sentinel(
    [("sentinel-1", 26379), ("sentinel-2", 26379), ("sentinel-3", 26379)],
    socket_timeout=0.5,
)
# master for writes, replica for reads
master = sentinel.master_for("mymaster", decode_responses=True)
replica = sentinel.slave_for("mymaster", decode_responses=True)

# Cluster (horizontal scaling)
from redis.asyncio.cluster import RedisCluster

cluster = RedisCluster.from_url("redis://node-1:7000", decode_responses=True)
await cluster.set("key", "value")   # routes to correct shard automatically
```

---

## Red Flags

- **No TTL on cache or session keys** — keys without expiry accumulate forever and evict randomly under memory pressure; set `ex=` on every `set()` call for cached data and sessions
- **Using pub/sub for reliable delivery** — pub/sub is fire-and-forget; subscribers that are offline when a message is published never receive it; use Redis Streams with consumer groups for any message that must not be lost
- **Single connection instead of a pool** — a single `await redis.from_url(...)` connection serializes all commands and blocks under concurrent load; use `ConnectionPool` with `max_connections` sized to your concurrency
- **`KEYS *` in production** — `KEYS` is O(n) and blocks the Redis event loop while it scans every key; use `SCAN` with a cursor to iterate non-blocking, or redesign to avoid key enumeration entirely
- **Distributed lock without a unique value** — a lock released by any caller using only the key (not the unique lock value) can accidentally release another owner's lock; always store a UUID as the value and use a Lua script to compare-then-delete atomically
- **Unbounded stream growth** — `xadd` without `maxlen` lets the stream grow indefinitely; always set `maxlen=N` (with `approximate=True` for efficiency) or run periodic `xtrim`
- **Sending multiple independent commands one at a time** — each `await client.set(...)` is a network round trip; batch three or more independent commands in a pipeline (`async with client.pipeline()`) to cut round-trip overhead significantly

## Checklist

- [ ] Connection pool used (not single connection) for async apps
- [ ] `decode_responses=True` set unless storing binary
- [ ] TTL set on all cache/session keys
- [ ] Pub/sub replaced with Streams where offline delivery matters
- [ ] `xack` called after processing stream messages (consumer groups)
- [ ] Pipeline used when sending ≥ 3 independent commands in sequence
- [ ] Distributed locks use NX + expiry to prevent deadlocks
- [ ] Sorted sets used for leaderboards / time-ordered data instead of sorted lists
- [ ] `maxlen` set on streams to prevent unbounded growth
