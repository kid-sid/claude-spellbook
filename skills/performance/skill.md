---
name: performance
description: "Application performance: CPU/memory/I/O profiling (cProfile+snakeviz, clinic.js+0x, pprof), caching strategies (in-process LRU, Redis, HTTP Cache-Control/ETags), database N+1 fix per ORM, async patterns for I/O vs CPU-bound work, and performance budgets tied to SLOs."
---

# Performance

A structured guide to profiling, caching, database optimization, async patterns, and performance budgets for production services.

## When to Activate

- Profiling a slow endpoint or service
- Implementing a caching layer (in-process, Redis, or HTTP)
- Optimizing a database query or fixing N+1 problems
- Setting a performance budget for an API endpoint
- Reducing memory usage or GC pressure
- Choosing between sync and async patterns for a workload

---

## Profiling

### When to Profile

- Profile before optimizing — never guess where the bottleneck is
- **CPU profiling** — where is time spent (function call time)?
- **Memory profiling** — what objects are consuming heap space?
- **I/O profiling** — what is blocking on disk or network?

### Python — cProfile + snakeviz

```python
import cProfile
import pstats
import io

pr = cProfile.Profile()
pr.enable()
result = my_slow_function()
pr.disable()

s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
ps.print_stats(20)  # top 20 slowest functions
print(s.getvalue())

# Profile a whole script from the command line:
# python -m cProfile -o output.prof script.py
# snakeviz output.prof  # opens interactive flame graph in browser
```

Memory profiling with `memory_profiler`:

```python
# pip install memory-profiler
from memory_profiler import profile

@profile
def my_function():
    # annotated line-by-line memory usage
    data = [x for x in range(10_000_000)]
    return data
```

### TypeScript/Node.js — clinic.js + 0x

```bash
# CPU flame graph
npx 0x -- node dist/server.js
# Opens a generated .html flame graph in the browser

# Heap snapshot + event loop lag
npx clinic doctor -- node dist/server.js

# CPU flame graph via clinic
npx clinic flame -- node dist/server.js

# Async waterfall / I/O bottlenecks
npx clinic bubbleprof -- node dist/server.js
```

### Go — pprof

```go
import (
    "net/http"
    _ "net/http/pprof" // side-effect import registers /debug/pprof handlers
)

// In main(), run alongside your app server:
go func() {
    http.ListenAndServe("localhost:6060", nil)
}()
```

```bash
# CPU profile (30-second sample)
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# Memory (heap) profile
go tool pprof http://localhost:6060/debug/pprof/heap

# In the pprof interactive prompt:
# (pprof) top10          — top 10 functions by CPU or memory
# (pprof) web            — open flame graph in browser (requires graphviz)
# (pprof) list FuncName  — annotated source with per-line costs
```

### Reading Flame Graphs

- **X-axis** — time (box width = proportion of total execution time)
- **Y-axis** — call stack depth (parent calls children above it)
- **Wide flat boxes near the top** — hot code paths; primary optimization targets
- **Long stacks with narrow top boxes** — deep recursion; usually not a problem
- **Plateaus** — the widest boxes in the middle of a stack often hide the real work

---

## Caching Strategies

### Strategy Comparison

| Strategy | Scope | Latency | Consistency | Best For |
|----------|-------|---------|-------------|----------|
| In-process LRU | Single instance | ~nanoseconds | Per-instance (inconsistent across replicas) | Immutable lookups, config, computed values |
| Distributed (Redis) | All instances | ~1 ms | Eventually consistent | Session state, rate limits, shared counters |
| HTTP cache (CDN/browser) | Client + CDN | ~0 ms on hit | TTL-based | Public read-heavy content, static assets |

### Cache-Aside Pattern (most common)

```python
def get_user(user_id: str) -> User:
    # 1. Check cache first
    cached = redis.get(f"user:{user_id}")
    if cached:
        return User.from_json(cached)

    # 2. Cache miss — fetch from DB
    user = db.query(User).filter(User.id == user_id).first()

    # 3. Populate cache with TTL
    redis.setex(f"user:{user_id}", 300, user.to_json())  # 5 min TTL
    return user
```

### Caching Pattern Comparison

| Pattern | Description | Consistency | Use When |
|---------|-------------|-------------|----------|
| Cache-aside | App manages cache reads and writes | Eventual | General purpose (most cases) |
| Read-through | Cache fetches from DB automatically on miss | Eventual | Simplify application read code |
| Write-through | Write to cache and DB synchronously | Strong | Read-heavy workloads needing consistency |
| Write-behind | Write to cache, async write to DB | Eventual | Write-heavy workloads that can accept risk |

### Cache Invalidation

- **TTL (time-to-live)** — simplest; accept stale data up to TTL duration
- **Event-driven** — invalidate on write (`redis.delete(f"user:{user_id}")` after UPDATE)
- **Write-through** — always write to both cache and DB; no stale data, but slower writes
- **Avoid** — invalidating cache on reads is an anti-pattern; adds latency to hot paths

### In-Process LRU Cache

```python
# Python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_config(key: str) -> str:
    return db.get_config(key)
```

```typescript
// TypeScript
import LRU from 'lru-cache';

const cache = new LRU<string, string>({ max: 1000, ttl: 1000 * 60 * 5 });

function getConfig(key: string): string {
  if (cache.has(key)) return cache.get(key)!;
  const value = db.getConfig(key);
  cache.set(key, value);
  return value;
}
```

```go
// Go
import "github.com/hashicorp/golang-lru/v2"

cache, _ := lru.New[string, string](1000)

func getConfig(key string) string {
    if val, ok := cache.Get(key); ok {
        return val
    }
    val := db.GetConfig(key)
    cache.Add(key, val)
    return val
}
```

---

## HTTP Cache Headers

| Header | Example Value | What It Controls |
|--------|--------------|-----------------|
| `Cache-Control` | `max-age=3600, s-maxage=86400` | Browser and CDN TTL |
| `ETag` | `"abc123"` | Version fingerprint for conditional requests |
| `Last-Modified` | `Wed, 15 Jan 2025 10:00:00 GMT` | Last modified time for conditional requests |
| `Vary` | `Accept-Encoding, Accept-Language` | Keys the cache on these request headers |

### Key `Cache-Control` Directives

| Directive | Meaning |
|-----------|---------|
| `max-age=N` | Browser caches for N seconds |
| `s-maxage=N` | CDN caches for N seconds (overrides `max-age` for CDN) |
| `no-cache` | Revalidate with server on every request (ETag/If-None-Match check) |
| `no-store` | Never cache (sensitive data) |
| `private` | Browser only — not stored by CDN |
| `stale-while-revalidate=N` | Serve stale while fetching fresh in background |
| `immutable` | Content will never change (pair with hash-based filenames) |

### Conditional Requests (ETag)

```http
# First request
GET /api/products/123
→ 200 OK
   ETag: "v2-abc123"
   Cache-Control: max-age=60

# After TTL expires — client sends ETag back
GET /api/products/123
If-None-Match: "v2-abc123"
→ 304 Not Modified   (no response body — saves bandwidth)
# or, if product changed:
→ 200 OK
   ETag: "v3-def456"
```

---

## Database N+1 Problem

### The Problem

```python
# BAD: N+1 — 1 query for orders + 1 query per order for its user
orders = db.query(Order).all()      # 1 query
for order in orders:
    print(order.user.name)          # N queries (lazy load per order)
```

With 500 orders this emits 501 queries. Use `EXPLAIN ANALYZE` or ORM query logging to detect this in review.

### Fix Per ORM

**Python — SQLAlchemy**

```python
from sqlalchemy.orm import selectinload, joinedload

# selectinload: 2 queries total — 1 for orders, 1 IN query for all related users
orders = db.query(Order).options(selectinload(Order.user)).all()

# joinedload: 1 query with a JOIN (better for single related object)
orders = db.query(Order).options(joinedload(Order.user)).all()
```

**TypeScript — Prisma**

```typescript
// BAD
const orders = await prisma.order.findMany();
for (const order of orders) {
  const user = await prisma.user.findUnique({ where: { id: order.userId } });
}

// GOOD — Prisma batches the related fetches automatically
const orders = await prisma.order.findMany({
  include: { user: true },
});
```

**Go — GORM**

```go
var orders []Order

// BAD — N separate queries inside the loop
db.Find(&orders)
for i := range orders {
    db.First(&orders[i].User, orders[i].UserID)
}

// GOOD — Preload issues a single IN query for all users
db.Preload("User").Find(&orders)
```

### Detecting N+1 in Practice

| Tool | How to Enable |
|------|--------------|
| SQLAlchemy | `echo=True` on `create_engine`, or use `sqlalchemy-query-counter` |
| Prisma | `log: ['query']` in `PrismaClient` constructor |
| GORM | `db.Debug()` or custom logger |
| Django ORM | `django-debug-toolbar` or `connection.queries` |
| General | `EXPLAIN ANALYZE SELECT ...` in psql to see sequential scans |

---

## Async Patterns

### I/O-Bound vs CPU-Bound

| Work Type | Python | TypeScript/Node.js | Go |
|-----------|--------|--------------------|----|
| I/O-bound (HTTP calls, DB) | `asyncio` / `async def` | `async/await` (native event loop) | goroutines (native) |
| CPU-bound (computation) | `ProcessPoolExecutor` (bypass GIL) | `worker_threads` module | goroutines (native, real parallelism) |
| Background jobs | Celery, RQ | BullMQ, Agenda | goroutines + channels |

### Python — asyncio for I/O-Bound Work

```python
import asyncio
import aiohttp

async def fetch_all(urls: list[str]) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, url) for url in urls]
        return await asyncio.gather(*tasks)  # concurrent, not parallel

async def fetch(session: aiohttp.ClientSession, url: str) -> dict:
    async with session.get(url) as response:
        return await response.json()
```

CPU-bound work in Python must use `ProcessPoolExecutor` to escape the GIL:

```python
from concurrent.futures import ProcessPoolExecutor

def cpu_heavy(data: list) -> int:
    return sum(x ** 2 for x in data)

async def process_many(chunks: list[list]) -> list[int]:
    loop = asyncio.get_event_loop()
    with ProcessPoolExecutor() as pool:
        results = await asyncio.gather(
            *[loop.run_in_executor(pool, cpu_heavy, chunk) for chunk in chunks]
        )
    return results
```

### TypeScript/Node.js — Protect the Event Loop

```typescript
import fs from 'fs';
import { Worker, isMainThread, workerData, parentPort } from 'worker_threads';

// BAD: sync read blocks the event loop for all requests
const data = fs.readFileSync('large-file.json', 'utf8');

// GOOD: async I/O — yields control back to event loop
const data = await fs.promises.readFile('large-file.json', 'utf8');

// BAD: CPU-heavy work in the main thread stalls all requests
const result = heavyComputation(data);

// GOOD: offload CPU work to a worker thread
function runInWorker(payload: unknown): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const worker = new Worker(__filename, { workerData: payload });
    worker.on('message', resolve);
    worker.on('error', reject);
  });
}
```

### Go — Goroutines for Concurrency

```go
// Fan-out: fire N goroutines, collect with WaitGroup + channel
func fetchAll(urls []string) []Result {
    results := make(chan Result, len(urls))
    var wg sync.WaitGroup

    for _, url := range urls {
        wg.Add(1)
        go func(u string) {
            defer wg.Done()
            resp, err := http.Get(u)
            results <- Result{URL: u, Err: err, Body: readBody(resp)}
        }(url)
    }

    wg.Wait()
    close(results)

    var out []Result
    for r := range results {
        out = append(out, r)
    }
    return out
}
```

---

## Performance Budgets

### Deriving a Budget from SLOs

- If the SLO is **p99 < 500 ms**, the internal service call budget is ~200 ms (leave headroom for network, serialization, retries)
- Decompose latency: `total = DB + cache + downstream API + serialization + middleware`
- Assign each component a share; the tightest constraint sets the overall shape

### Endpoint Budget Reference

| Endpoint Category | p50 Target | p99 Target |
|-------------------|-----------|-----------|
| Read-only lookups | < 50 ms | < 200 ms |
| Search / aggregation | < 200 ms | < 1 s |
| Write operations | < 100 ms | < 500 ms |
| Background jobs | N/A | N/A (use queue depth + processing lag metrics) |

### CI Regression Detection

```yaml
# k6 threshold example — fails the PR if p99 regresses
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  thresholds: {
    http_req_duration: ['p(99)<500'],  // fail if p99 > 500ms
  },
};

export default function () {
  const res = http.get('http://localhost:3000/api/users/1');
  check(res, { 'status 200': (r) => r.status === 200 });
}
```

Run this in CI on every PR:

```bash
k6 run --vus 50 --duration 30s load-test.js
# Exit code non-zero if any threshold is breached
```

Fail the build if p99 degrades more than 20% from the baseline captured on `main`.

> See also: `database-design`, `observability`, `performance-testing`

---

## Checklist

- [ ] Profiled before optimizing — no premature optimization
- [ ] Flame graph or profile output captured to identify the actual bottleneck
- [ ] N+1 queries detected with `EXPLAIN ANALYZE` or ORM query logging
- [ ] Eager loading configured for all related-entity fetches
- [ ] Cache layer added for hot read paths (in-process for single-instance, Redis for distributed)
- [ ] Cache keys include version or tenant identifier to prevent cross-user data leaks
- [ ] `Cache-Control` headers set for all public API responses
- [ ] ETags implemented for cacheable resources (304 responses save bandwidth)
- [ ] `async/await` or equivalent used for all I/O-bound operations
- [ ] CPU-bound work offloaded to worker processes or threads
- [ ] Performance budget defined per endpoint category and documented
- [ ] Baseline p50/p95/p99 measured before and after changes
