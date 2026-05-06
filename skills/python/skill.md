---
name: python
description: Use when writing or debugging non-trivial Python — async pitfalls, type system patterns, dataclass vs Pydantic decisions, decorator design, generator efficiency, or language-specific idioms like structural pattern matching and slots.
---

# Python — Advanced Patterns

Language-level patterns for writing correct, readable, performant Python.

## When to Activate

- Choosing between dataclasses, TypedDict, NamedTuple, or Pydantic models
- Designing type annotations with generics, Protocols, or `TypeVar`
- Writing or debugging async code (`async`/`await`, event loops, `asyncio`)
- Building decorators, context managers, or generators
- Using `itertools`, `functools`, or comprehensions effectively
- Applying structural pattern matching (`match`/`case`)
- Performance micro-optimisations (`__slots__`, `lru_cache`, generators vs lists)

---

## Type Hints

### Built-in generics (Python 3.10+)

```python
# Use built-in types directly — no need to import from typing
def process(items: list[str]) -> dict[str, int]: ...
def fetch(ids: set[int]) -> tuple[str, ...]: ...
def map_fn(data: dict[str, list[int]]) -> None: ...

# Union with | (3.10+)
def parse(value: str | int | None) -> str: ...

# TypeAlias
type UserId = str           # Python 3.12+
UserId = NewType("UserId", str)  # Python 3.10+
```

### TypeVar and Generics

```python
from typing import TypeVar, Generic

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")

def first(items: list[T]) -> T | None:
    return items[0] if items else None

class Repository(Generic[T]):
    async def get(self, id: str) -> T | None: ...
    async def save(self, entity: T) -> T: ...

class UserRepository(Repository[User]): ...  # T = User
```

### Protocol — structural subtyping (duck typing with types)

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Closeable(Protocol):
    def close(self) -> None: ...

@runtime_checkable
class Serializable(Protocol):
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> "Serializable": ...

# Any class with these methods satisfies the protocol — no inheritance needed
def cleanup(resource: Closeable) -> None:
    resource.close()
```

### Annotated — attach metadata to types

```python
from typing import Annotated
from pydantic import Field

# Reusable constrained types
PositiveInt = Annotated[int, Field(gt=0)]
EmailStr = Annotated[str, Field(pattern=r".+@.+")]
UserId = Annotated[str, Field(min_length=36, max_length=36)]

class User(BaseModel):
    id: UserId
    age: PositiveInt
    email: EmailStr
```

### Literal and TypeGuard

```python
from typing import Literal, TypeGuard

Status = Literal["active", "inactive", "banned"]

def is_active(status: Status) -> TypeGuard[Literal["active"]]:
    return status == "active"

# TypedDict for dict shapes
from typing import TypedDict

class UserDict(TypedDict):
    id: str
    name: str
    email: str

class PartialUserDict(TypedDict, total=False):
    name: str
    email: str
```

---

## Dataclasses vs Pydantic vs TypedDict

| | Dataclass | Pydantic | TypedDict | NamedTuple |
|---|---|---|---|---|
| Runtime validation | ❌ | ✅ | ❌ | ❌ |
| Immutable option | `frozen=True` | `frozen=True` | ❌ | ✅ (always) |
| JSON serialization | manual | `.model_dump()` | manual | manual |
| Inheritance | ✅ | ✅ | limited | ❌ |
| Performance | fastest | moderate | dict | fast |
| Use when | internal data transfer | API schemas, config | typed dict hints | simple immutable tuples |

```python
from dataclasses import dataclass, field

@dataclass
class Point:
    x: float
    y: float
    tags: list[str] = field(default_factory=list)  # mutable default must use field()

@dataclass(frozen=True)   # immutable, hashable
class Color:
    r: int; g: int; b: int

@dataclass(slots=True)    # __slots__ automatically (Python 3.10+)
class FastModel:
    name: str
    value: int
```

---

## Async / Await

### Pitfalls

```python
# BAD: sync sleep blocks the entire event loop
async def handler():
    time.sleep(1)           # freezes all other coroutines

# GOOD: async sleep yields control
async def handler():
    await asyncio.sleep(1)  # other coroutines run while waiting

# BAD: sync I/O in async code (blocks event loop)
async def read_file():
    return open("file.txt").read()  # blocking

# GOOD: use aiofiles or run in executor
import aiofiles
async def read_file():
    async with aiofiles.open("file.txt") as f:
        return await f.read()

# Run blocking code in thread pool (for libraries you can't change)
import asyncio
result = await asyncio.get_event_loop().run_in_executor(None, blocking_function, arg)
```

### Concurrency patterns

```python
import asyncio

# Run independent coroutines concurrently
results = await asyncio.gather(
    fetch_user(id),
    fetch_orders(id),
    fetch_profile(id),
)
user, orders, profile = results

# gather with error handling
results = await asyncio.gather(fetch_a(), fetch_b(), return_exceptions=True)
for r in results:
    if isinstance(r, Exception):
        handle_error(r)

# TaskGroup (Python 3.11+) — cancels all tasks if one fails
async with asyncio.TaskGroup() as tg:
    task_a = tg.create_task(fetch_a())
    task_b = tg.create_task(fetch_b())
# both results available after the block

# Timeout
try:
    result = await asyncio.wait_for(slow_operation(), timeout=5.0)
except asyncio.TimeoutError:
    handle_timeout()

# Semaphore — limit concurrency (e.g. max 10 concurrent HTTP requests)
sem = asyncio.Semaphore(10)
async def rate_limited_fetch(url):
    async with sem:
        return await httpx.get(url)
```

### Async generators and context managers

```python
# Async generator
async def paginate(url: str):
    page = 1
    while True:
        data = await fetch(f"{url}?page={page}")
        if not data:
            break
        yield data
        page += 1

async for batch in paginate("/api/items"):
    process(batch)

# Async context manager
class AsyncDB:
    async def __aenter__(self):
        self.conn = await connect()
        return self.conn

    async def __aexit__(self, *args):
        await self.conn.close()

async with AsyncDB() as conn:
    await conn.execute("SELECT 1")
```

---

## Context Managers

```python
from contextlib import contextmanager, asynccontextmanager, suppress

# Synchronous
@contextmanager
def timer(label: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        print(f"{label}: {time.perf_counter() - start:.3f}s")

with timer("query"):
    result = db.execute(query)

# Async
@asynccontextmanager
async def db_transaction(session):
    async with session.begin():
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

# Suppress specific exceptions
with suppress(FileNotFoundError):
    os.remove("tmp.txt")

# ExitStack — combine multiple context managers dynamically
from contextlib import ExitStack

with ExitStack() as stack:
    files = [stack.enter_context(open(f)) for f in file_list]
    process(files)
```

---

## Decorators

```python
from functools import wraps
import time

# Basic decorator with functools.wraps (preserves __name__, __doc__)
def retry(max_attempts: int = 3, delay: float = 1.0):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await fn(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    await asyncio.sleep(delay * (attempt + 1))
        return wrapper
    return decorator

@retry(max_attempts=3, delay=0.5)
async def fetch_data(url: str) -> dict: ...

# Class-based decorator (useful when the decorator needs state)
class RateLimit:
    def __init__(self, calls: int, period: float):
        self.calls = calls
        self.period = period
        self.timestamps: list[float] = []

    def __call__(self, fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            now = time.time()
            self.timestamps = [t for t in self.timestamps if now - t < self.period]
            if len(self.timestamps) >= self.calls:
                raise Exception("Rate limit exceeded")
            self.timestamps.append(now)
            return await fn(*args, **kwargs)
        return wrapper
```

---

## Generators and itertools

```python
import itertools

# Generator — lazy, memory-efficient
def read_chunks(path: str, size: int = 4096):
    with open(path, "rb") as f:
        while chunk := f.read(size):
            yield chunk

# Generator expression
total = sum(x ** 2 for x in range(1_000_000))  # no list in memory

# itertools
list(itertools.islice(range(100), 10))          # first 10
list(itertools.chain([1,2], [3,4], [5,6]))      # flatten iterables
list(itertools.batched([1..9], 3))              # [[1,2,3],[4,5,6],[7,8,9]] (3.12+)
list(itertools.groupby(sorted_items, key=lambda x: x.category))
list(itertools.takewhile(lambda x: x < 5, items))
list(itertools.dropwhile(lambda x: x < 5, items))
list(itertools.pairwise([1,2,3,4]))             # [(1,2),(2,3),(3,4)] (3.10+)

# functools
from functools import lru_cache, cached_property, reduce, partial

@lru_cache(maxsize=128)
def fibonacci(n: int) -> int:
    return n if n < 2 else fibonacci(n-1) + fibonacci(n-2)

class Config:
    @cached_property        # computed once, cached on instance
    def parsed_rules(self) -> list[Rule]:
        return parse_rules(self.raw)

double = partial(operator.mul, 2)   # partial application
```

---

## Structural Pattern Matching (Python 3.10+)

```python
def handle_event(event: dict):
    match event:
        case {"type": "user_created", "data": {"id": user_id, "email": email}}:
            create_user(user_id, email)

        case {"type": "order_placed", "data": {"total": total}} if total > 1000:
            flag_high_value_order(event)

        case {"type": str(t)} if t.startswith("payment_"):
            handle_payment(event)

        case _:
            log_unknown(event)

# Match on types
def process(value):
    match value:
        case int(n) if n > 0:   return f"positive int: {n}"
        case str(s):            return f"string: {s}"
        case [*items]:          return f"list of {len(items)}"
        case {"key": v}:        return f"dict with key: {v}"
        case None:              return "nothing"
```

---

## `__slots__`

Reduces memory per instance by ~40-60% for classes with many instances. Prevents arbitrary attribute assignment.

```python
class Point:
    __slots__ = ("x", "y")   # no __dict__, no __weakref__ by default

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

# With inheritance: each class only declares its own new slots
class Point3D(Point):
    __slots__ = ("z",)        # inherits x, y slots from Point
```

Use `slots=True` on dataclasses: `@dataclass(slots=True)`.

---

## Common Gotchas

```python
# Mutable default argument — shared across all calls
def bad(items=[]):      items.append(1)  # BAD — list is shared
def good(items=None):   items = items or []  # GOOD

# Late binding in closures
fns = [lambda x, i=i: x + i for i in range(3)]  # i=i captures current value

# is vs ==
a = 256; b = 256; a is b   # True  — small ints are cached
a = 257; b = 257; a is b   # False — large ints are not
# Always use == for value equality; is only for None/True/False/singletons

# Walrus operator := (Python 3.8+)
while chunk := file.read(8192):
    process(chunk)

if m := re.search(pattern, text):
    print(m.group(0))

# Exception chaining
try:
    result = parse(data)
except ValueError as e:
    raise ServiceError("Parse failed") from e  # preserves original traceback

# f-string debugging (Python 3.8+)
x = 42
print(f"{x=}")  # prints: x=42
```

---

## Performance Tips

| Technique | When to use |
|---|---|
| `__slots__` | Many instances of the same class in memory |
| `@lru_cache` | Pure functions called repeatedly with same args |
| Generator over list | Large sequences you iterate once |
| `collections.deque` | Frequent append/pop from both ends |
| `set` lookup | `x in large_collection` — O(1) vs O(n) for list |
| `str.join` | Building strings in a loop — never `+=` in a loop |
| `local variable` | Hoist `self.attr` to local in tight loops |
| `asyncio.gather` | Independent async calls — run concurrently |

---

## Red Flags

- **Mutable default arguments** (`def f(items=[])`) — the default list is created once at definition time and shared across all calls; use `None` as the default and initialize inside the function body
- **Bare `except:` or `except Exception:`** — catching all exceptions hides bugs and swallows `KeyboardInterrupt`; catch the narrowest specific exception type you actually expect and handle
- **`asyncio.run()` inside an already-running event loop** — calling `asyncio.run()` from within an async context (FastAPI, Jupyter) raises `RuntimeError`; use `await` directly or `loop.run_until_complete()`
- **Threads for CPU-bound work** — Python's GIL prevents true thread parallelism for CPU tasks; use `multiprocessing` or `ProcessPoolExecutor` for CPU-bound parallelism
- **`from module import *` in `__init__.py`** — star imports pollute the namespace and make name origins untraceable; always import explicitly
- **`@dataclass` fields with mutable defaults** — `field: list = []` shares the same list object across all instances; use `field(default_factory=list)` for mutable defaults
- **`is` to compare values** — `x is 1` or `x is "hello"` relies on CPython interning that is not guaranteed across Python versions; use `==` for value comparison and `is` only for `None`, `True`, `False`

## Checklist

- [ ] Type hints on all public functions and method signatures
- [ ] `Protocol` used instead of ABC when only structural compatibility matters
- [ ] Mutable defaults use `field(default_factory=...)` in dataclasses
- [ ] Async code uses `asyncio.sleep`, `aiofiles`, or `run_in_executor` — never `time.sleep`
- [ ] Independent async calls use `asyncio.gather` or `TaskGroup`
- [ ] Decorators use `@functools.wraps` to preserve function metadata
- [ ] `@lru_cache` on pure, frequently-called functions
- [ ] `__slots__` on dataclasses or classes with many instances
- [ ] `suppress` / `ExitStack` from `contextlib` instead of try/finally boilerplate
