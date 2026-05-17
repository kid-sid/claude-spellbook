---
name: error-handling
description: Use when designing error hierarchies, propagating errors across service boundaries, implementing retry and backoff logic, writing structured error responses for APIs, or making error handling consistent across a Python, TypeScript, or Go codebase.
---

# Error Handling

Patterns for structured errors, propagation, retries, and consistent failure surfaces across Python, TypeScript, and Go.

## When to Activate

- Designing a custom exception or error hierarchy for a service
- Propagating errors across HTTP, gRPC, or queue boundaries
- Implementing retry logic with exponential backoff and jitter
- Writing consistent error responses for a REST or GraphQL API
- Distinguishing recoverable from unrecoverable errors
- Auditing a codebase for swallowed exceptions or bare `except` blocks
- Adding context to errors without losing the original cause

---

## Error Classification

Classify errors before deciding how to handle them — the right response depends on what kind of failure occurred.

| Class | Examples | Handle by |
|---|---|---|
| Validation | Missing field, bad format | Return 400 immediately — no retry |
| Not found | Unknown ID, deleted resource | Return 404 — no retry |
| Auth | Invalid token, expired session | Return 401/403 — no retry |
| Transient | Network timeout, DB connection blip | Retry with backoff |
| Dependency | Third-party API down, queue unavailable | Retry, then circuit-break |
| Logic bug | Null deref, assertion failure | Log + alert — do not retry or swallow |
| Rate limited | 429 from upstream | Retry after `Retry-After` header |

---

## Custom Error Hierarchies

### Python

```python
# Base domain error — all app errors inherit from this
class AppError(Exception):
    def __init__(self, message: str, code: str, status: int = 500) -> None:
        super().__init__(message)
        self.code = code
        self.status = status

class NotFoundError(AppError):
    def __init__(self, resource: str, id: str) -> None:
        super().__init__(f"{resource} '{id}' not found", "NOT_FOUND", 404)

class ValidationError(AppError):
    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"Invalid '{field}': {reason}", "VALIDATION_ERROR", 400)

class TransientError(AppError):
    """Signals a retry is safe."""
    def __init__(self, message: str) -> None:
        super().__init__(message, "TRANSIENT_ERROR", 503)
```

### TypeScript

```typescript
// Tagged union — exhaustive handling without instanceof chains
type AppError =
  | { tag: "NOT_FOUND"; resource: string; id: string }
  | { tag: "VALIDATION"; field: string; reason: string }
  | { tag: "UNAUTHORIZED" }
  | { tag: "TRANSIENT"; message: string; retryable: true };

function notFound(resource: string, id: string): AppError {
  return { tag: "NOT_FOUND", resource, id };
}

// Result type — explicit error path, no throw/catch in business logic
type Result<T, E = AppError> = { ok: true; value: T } | { ok: false; error: E };

function ok<T>(value: T): Result<T> { return { ok: true, value }; }
function err<E>(error: E): Result<never, E> { return { ok: false, error }; }

// Usage
async function getUser(id: string): Promise<Result<User>> {
  const user = await db.findUser(id);
  if (!user) return err(notFound("User", id));
  return ok(user);
}

const result = await getUser("123");
if (!result.ok) {
  // result.error is fully typed here
  switch (result.error.tag) {
    case "NOT_FOUND": return res.status(404).json({ error: result.error });
    case "UNAUTHORIZED": return res.status(401).json({ error: "Unauthorized" });
  }
}
```

### Go

```go
// Sentinel errors for classification
var (
    ErrNotFound   = errors.New("not found")
    ErrValidation = errors.New("validation error")
    ErrTransient  = errors.New("transient error")
)

// Structured error with context
type AppError struct {
    Code    string
    Message string
    Err     error  // wrapped cause
}

func (e *AppError) Error() string { return e.Message }
func (e *AppError) Unwrap() error { return e.Err }

func NotFound(resource, id string) *AppError {
    return &AppError{
        Code:    "NOT_FOUND",
        Message: fmt.Sprintf("%s '%s' not found", resource, id),
        Err:     ErrNotFound,
    }
}

// Propagate with context — never discard the original error
func getUser(ctx context.Context, id string) (*User, error) {
    user, err := db.FindUser(ctx, id)
    if err != nil {
        if errors.Is(err, sql.ErrNoRows) {
            return nil, NotFound("User", id)
        }
        return nil, fmt.Errorf("getUser %s: %w", id, err)
    }
    return user, nil
}

// Check error class at the boundary
if errors.Is(err, ErrNotFound) {
    http.Error(w, "Not found", http.StatusNotFound)
    return
}
if errors.Is(err, ErrTransient) {
    http.Error(w, "Service unavailable", http.StatusServiceUnavailable)
    return
}
```

---

## Adding Context Without Losing the Cause

```python
# Python — chain exceptions
try:
    result = db.query(sql)
except psycopg2.OperationalError as exc:
    raise TransientError("database unavailable") from exc  # preserves __cause__

# BAD — swallows the original traceback
raise TransientError("database unavailable")
```

```typescript
// TypeScript — wrap with cause
throw new Error("Database unavailable", { cause: originalError });

// BAD — loses original stack
throw new Error("Database unavailable");
```

```go
// Go — %w verb wraps for errors.Is / errors.As
return fmt.Errorf("fetchOrders: %w", err)   // ✓ preserves chain

// BAD — breaks unwrapping
return fmt.Errorf("fetchOrders: %v", err)   // ✗ wraps as string only
return errors.New("fetchOrders failed")     // ✗ discards original
```

---

## Retry with Exponential Backoff and Jitter

Jitter prevents thundering herd when many callers retry simultaneously.

```python
# Python
import asyncio, random

async def with_retry(fn, *, max_attempts: int = 3, base_delay: float = 0.5):
    for attempt in range(max_attempts):
        try:
            return await fn()
        except TransientError:
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.3)
            await asyncio.sleep(delay)
```

```typescript
// TypeScript
async function withRetry<T>(
  fn: () => Promise<T>,
  { maxAttempts = 3, baseDelay = 500 } = {}
): Promise<T> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      if (!isRetryable(err) || attempt === maxAttempts - 1) throw err;
      const delay = baseDelay * 2 ** attempt + Math.random() * 300;
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  throw new Error("unreachable");
}

function isRetryable(err: unknown): boolean {
  return err instanceof AppError && err.tag === "TRANSIENT";
}
```

```go
// Go
func WithRetry(ctx context.Context, fn func() error, maxAttempts int) error {
    var err error
    for attempt := range maxAttempts {
        if err = fn(); err == nil {
            return nil
        }
        if !errors.Is(err, ErrTransient) {
            return err
        }
        if attempt == maxAttempts-1 {
            break
        }
        delay := time.Duration(math.Pow(2, float64(attempt))*500)*time.Millisecond +
            time.Duration(rand.Intn(300))*time.Millisecond
        select {
        case <-time.After(delay):
        case <-ctx.Done():
            return ctx.Err()
        }
    }
    return fmt.Errorf("after %d attempts: %w", maxAttempts, err)
}
```

---

## Structured API Error Responses

Every API error should include: machine-readable `code`, human-readable `message`, optional `details` for field-level problems.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      { "field": "email", "reason": "must be a valid email address" },
      { "field": "age",   "reason": "must be a positive integer" }
    ],
    "request_id": "req_01HX..."
  }
}
```

```python
# FastAPI global handler
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {
                "code": exc.code,
                "message": str(exc),
                "request_id": request.state.request_id,
            }
        },
    )
```

```typescript
// Express global error handler — must be last middleware
app.use((err: unknown, req: Request, res: Response, _next: NextFunction) => {
  const requestId = req.headers["x-request-id"] ?? crypto.randomUUID();
  if (err instanceof AppError) {
    return res.status(err.status).json({
      error: { code: err.code, message: err.message, request_id: requestId },
    });
  }
  console.error("Unhandled error", err);
  res.status(500).json({
    error: { code: "INTERNAL_ERROR", message: "An unexpected error occurred", request_id: requestId },
  });
});
```

---

## Logging Errors

| Severity | When | Fields to include |
|---|---|---|
| `ERROR` | Unhandled or unexpected failures | message, stack, request_id, user_id |
| `WARN` | Handled but notable (retry succeeded, degraded mode) | message, attempt count |
| `INFO` | Expected failures returned to caller (404, 400) | code, path — no stack trace |
| `DEBUG` | Retry attempts, circuit state | attempt, delay, error message |

```python
# BAD — log and re-raise doubles the noise
except SomeError as exc:
    logger.error("Failed", exc_info=True)
    raise  # logged again by the global handler

# GOOD — log once at the boundary, propagate elsewhere
except SomeError as exc:
    raise TransientError("upstream failed") from exc  # logged once at the top
```

---

## Red Flags

- **Bare `except` / `catch (e) {}`** — swallows the error entirely; always re-raise or handle explicitly.
- **Retrying non-retryable errors** — retrying a 400 or 404 wastes time and can amplify load; check error class before retrying.
- **`raise Exception("something went wrong")`** — generic base types give callers no way to branch; use typed domain errors.
- **Logging and re-raising at every layer** — logs the same error multiple times; propagate up and log once at the boundary.
- **Using `%v` instead of `%w` in Go** — breaks `errors.Is` / `errors.As` unwrapping; always use `%w` when wrapping.
- **Ignoring `err` in Go** — `_ = fn()` silently discards failures; use `//nolint:errcheck` only with a documented reason.
- **No `request_id` in error responses** — makes support and debugging impossible; always include a correlation ID.
- **Returning 500 for client errors** — masks bugs; map domain errors to the correct 4xx before they reach the handler.
- **Retry without jitter** — synchronized retries hammer a recovering dependency; always add random jitter.

---

## Checklist

- [ ] Custom error types carry `code`, `message`, and HTTP `status` — no raw `Exception("string")` at boundaries
- [ ] Errors are wrapped with context at each layer (`from exc` / `{ cause }` / `%w`) — original cause preserved
- [ ] Error class determined before retrying — only `TRANSIENT` errors retried, never validation or auth errors
- [ ] Retry uses exponential backoff with jitter — no fixed-interval loops
- [ ] Global error handler present — no unhandled errors reaching the framework default
- [ ] API error responses include `code`, `message`, and `request_id` — consistent shape across all endpoints
- [ ] Errors logged once at the top boundary — not re-logged at every layer
- [ ] `INFO` used for expected 4xx, `ERROR` for unexpected 5xx — no stack traces in 404 logs
- [ ] Go functions never ignore `error` return values without a documented reason
- [ ] Circuit breaker or fallback present for calls to external dependencies
