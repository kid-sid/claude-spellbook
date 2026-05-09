---
name: go
description: Use when writing or debugging non-trivial Go — error handling patterns, goroutine/channel design, interface composition, generics, context propagation, or Go-specific idioms like table-driven tests and functional options.
---

# Go — Advanced Patterns

Language-level patterns for writing correct, idiomatic, performant Go.

## When to Activate

- Designing error types, wrapping, and sentinel errors
- Structuring goroutines, channels, and `sync` primitives correctly
- Propagating `context.Context` for cancellation and deadlines
- Composing interfaces and embedding types
- Using generics (`any`, constraints, type parameters) appropriately
- Writing table-driven tests, benchmarks, or fuzz targets
- Applying functional options, builder patterns, or the options struct pattern
- Structuring packages, modules, and internal vs exported APIs

---

## Error Handling

### Wrapping and unwrapping

```go
import "errors"

// Wrap to add context — preserves the original for errors.Is/As
if err != nil {
    return fmt.Errorf("fetch user %d: %w", id, err)
}

// Sentinel errors — compare with errors.Is (not ==)
var ErrNotFound = errors.New("not found")
var ErrUnauthorized = errors.New("unauthorized")

if errors.Is(err, ErrNotFound) {
    // handle not found
}

// Custom error type — use errors.As to extract
type ValidationError struct {
    Field   string
    Message string
}
func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation error on %s: %s", e.Field, e.Message)
}

var ve *ValidationError
if errors.As(err, &ve) {
    log.Printf("invalid field: %s", ve.Field)
}
```

### Multiple return errors

```go
// BAD: ignoring errors
data, _ := os.ReadFile("config.json")

// GOOD: always handle
data, err := os.ReadFile("config.json")
if err != nil {
    return fmt.Errorf("read config: %w", err)
}

// Return early, keep the happy path unindented
func process(id string) (*Result, error) {
    user, err := db.GetUser(id)
    if err != nil {
        return nil, fmt.Errorf("get user: %w", err)
    }
    orders, err := db.GetOrders(id)
    if err != nil {
        return nil, fmt.Errorf("get orders: %w", err)
    }
    return &Result{User: user, Orders: orders}, nil
}
```

---

## Goroutines and Channels

### Goroutine lifecycle — always have an exit strategy

```go
// BAD: goroutine leaks — no way to stop it
go func() {
    for {
        process()
    }
}()

// GOOD: context-driven shutdown
func worker(ctx context.Context, jobs <-chan Job) {
    for {
        select {
        case <-ctx.Done():
            return
        case job, ok := <-jobs:
            if !ok {
                return  // channel closed
            }
            process(job)
        }
    }
}
```

### Fan-out / fan-in

```go
func fanOut(ctx context.Context, in <-chan int, workers int) <-chan Result {
    out := make(chan Result)
    var wg sync.WaitGroup

    for i := 0; i < workers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for v := range in {
                select {
                case out <- compute(v):
                case <-ctx.Done():
                    return
                }
            }
        }()
    }

    go func() {
        wg.Wait()
        close(out)  // signal downstream that all workers are done
    }()
    return out
}
```

### Channel patterns

```go
// Done channel — broadcast shutdown to many goroutines
done := make(chan struct{})
close(done)             // unblocks ALL receivers simultaneously

// Buffered channel as semaphore — limit concurrency
sem := make(chan struct{}, 10)
sem <- struct{}{}       // acquire
defer func() { <-sem }() // release

// Pipeline stage
func generate(nums ...int) <-chan int {
    out := make(chan int)
    go func() {
        defer close(out)
        for _, n := range nums {
            out <- n
        }
    }()
    return out
}

// Select with default — non-blocking send/receive
select {
case ch <- value:
    // sent
default:
    // channel full — drop or handle
}
```

### `sync` primitives

```go
// Mutex — protect shared state
type SafeCounter struct {
    mu    sync.Mutex
    count map[string]int
}
func (c *SafeCounter) Inc(key string) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count[key]++
}

// RWMutex — concurrent reads, exclusive writes
type Cache struct {
    mu    sync.RWMutex
    store map[string]string
}
func (c *Cache) Get(k string) (string, bool) {
    c.mu.RLock()
    defer c.mu.RUnlock()
    v, ok := c.store[k]
    return v, ok
}

// sync.Once — initialize exactly once (safe for goroutines)
var instance *DB
var once sync.Once
func GetDB() *DB {
    once.Do(func() { instance = connect() })
    return instance
}

// sync.WaitGroup — wait for a collection of goroutines
var wg sync.WaitGroup
for _, item := range items {
    wg.Add(1)
    go func(i Item) {
        defer wg.Done()
        process(i)
    }(item)
}
wg.Wait()
```

---

## Context

```go
// Always accept context as the first parameter in public functions
func FetchUser(ctx context.Context, id string) (*User, error) { ... }

// Propagate — never store context in structs
type Service struct{ db *DB }  // GOOD — context passed per call
func (s *Service) Get(ctx context.Context, id string) (*User, error) { ... }

// Deadline / timeout
ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
defer cancel()  // always defer cancel — releases resources even on success

// Cancellation
ctx, cancel := context.WithCancel(context.Background())
go worker(ctx)
cancel()  // signal worker to stop

// Value — only for request-scoped data (trace IDs, auth tokens), not config
type ctxKey string
const requestIDKey ctxKey = "requestID"

func WithRequestID(ctx context.Context, id string) context.Context {
    return context.WithValue(ctx, requestIDKey, id)
}
func RequestID(ctx context.Context) string {
    v, _ := ctx.Value(requestIDKey).(string)
    return v
}

// Check cancellation in long loops
for _, item := range largeSlice {
    if ctx.Err() != nil {
        return ctx.Err()
    }
    process(item)
}
```

---

## Interfaces and Embedding

### Interface design — small, composable

```go
// BAD: fat interface — hard to implement, hard to test
type Storage interface {
    Get(id string) (*User, error)
    Save(u *User) error
    Delete(id string) error
    List(filter Filter) ([]*User, error)
    Search(q string) ([]*User, error)
    Count() (int, error)
}

// GOOD: small, focused interfaces
type UserGetter interface {
    GetUser(ctx context.Context, id string) (*User, error)
}
type UserSaver interface {
    SaveUser(ctx context.Context, u *User) error
}
// Compose only where needed
type UserStore interface {
    UserGetter
    UserSaver
}

// Accept interfaces, return structs
func NewService(store UserGetter) *Service { ... }  // testable
func NewPostgresStore(db *sql.DB) *PostgresStore { ... }  // concrete return
```

### Embedding

```go
// Struct embedding — promotes fields and methods
type Animal struct{ Name string }
func (a Animal) Speak() string { return a.Name }

type Dog struct {
    Animal              // promoted: dog.Name, dog.Speak()
    Breed string
}

// Interface embedding
type ReadWriter interface {
    io.Reader
    io.Writer
}

// Embedding to extend without inheriting
type LoggedStore struct {
    Store          // delegates all Store methods
    log *slog.Logger
}
func (ls *LoggedStore) GetUser(ctx context.Context, id string) (*User, error) {
    u, err := ls.Store.GetUser(ctx, id)  // delegate
    ls.log.Info("get user", "id", id, "err", err)
    return u, err
}
```

---

## Functional Options Pattern

Preferred over long constructor signatures or config structs that need zero values to be meaningful.

```go
type Server struct {
    host    string
    port    int
    timeout time.Duration
    logger  *slog.Logger
}

type Option func(*Server)

func WithPort(p int) Option        { return func(s *Server) { s.port = p } }
func WithTimeout(d time.Duration) Option { return func(s *Server) { s.timeout = d } }
func WithLogger(l *slog.Logger) Option   { return func(s *Server) { s.logger = l } }

func NewServer(host string, opts ...Option) *Server {
    s := &Server{host: host, port: 8080, timeout: 30 * time.Second}
    for _, opt := range opts {
        opt(s)
    }
    return s
}

// Usage
srv := NewServer("localhost",
    WithPort(9090),
    WithTimeout(10*time.Second),
    WithLogger(slog.Default()),
)
```

---

## Generics

```go
// Type constraint — built-in or custom
type Number interface {
    ~int | ~int32 | ~int64 | ~float32 | ~float64
}

func Sum[T Number](items []T) T {
    var total T
    for _, v := range items {
        total += v
    }
    return total
}

// Generic data structures
type Stack[T any] struct {
    items []T
}
func (s *Stack[T]) Push(v T) { s.items = append(s.items, v) }
func (s *Stack[T]) Pop() (T, bool) {
    var zero T
    if len(s.items) == 0 {
        return zero, false
    }
    v := s.items[len(s.items)-1]
    s.items = s.items[:len(s.items)-1]
    return v, true
}

// Map / Filter helpers
func Map[T, U any](slice []T, fn func(T) U) []U {
    result := make([]U, len(slice))
    for i, v := range slice {
        result[i] = fn(v)
    }
    return result
}

func Filter[T any](slice []T, fn func(T) bool) []T {
    var result []T
    for _, v := range slice {
        if fn(v) {
            result = append(result, v)
        }
    }
    return result
}
```

---

## HTTP Patterns (net/http)

```go
// Handler with dependencies — use a method, not a closure
type Handler struct {
    svc *UserService
    log *slog.Logger
}

func (h *Handler) GetUser(w http.ResponseWriter, r *http.Request) {
    id := r.PathValue("id")  // Go 1.22+ built-in path params
    user, err := h.svc.Get(r.Context(), id)
    if err != nil {
        if errors.Is(err, ErrNotFound) {
            http.Error(w, "not found", http.StatusNotFound)
            return
        }
        h.log.Error("get user", "err", err)
        http.Error(w, "internal error", http.StatusInternalServerError)
        return
    }
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(user)
}

// Routing (Go 1.22+)
mux := http.NewServeMux()
mux.HandleFunc("GET /users/{id}", h.GetUser)
mux.HandleFunc("POST /users", h.CreateUser)

// Middleware chaining
func logging(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()
        next.ServeHTTP(w, r)
        slog.Info("request", "method", r.Method, "path", r.URL.Path, "dur", time.Since(start))
    })
}

srv := &http.Server{
    Addr:         ":8080",
    Handler:      logging(mux),
    ReadTimeout:  5 * time.Second,
    WriteTimeout: 10 * time.Second,
    IdleTimeout:  120 * time.Second,
}
```

---

## Testing

### Table-driven tests

```go
func TestAdd(t *testing.T) {
    cases := []struct {
        name string
        a, b int
        want int
    }{
        {"positive", 1, 2, 3},
        {"negative", -1, -2, -3},
        {"zero", 0, 0, 0},
    }
    for _, tc := range cases {
        t.Run(tc.name, func(t *testing.T) {
            got := Add(tc.a, tc.b)
            if got != tc.want {
                t.Errorf("Add(%d, %d) = %d, want %d", tc.a, tc.b, got, tc.want)
            }
        })
    }
}
```

### Test helpers and cleanup

```go
func setupDB(t *testing.T) *sql.DB {
    t.Helper()  // marks this as a helper — errors show caller's line
    db, err := sql.Open("sqlite3", ":memory:")
    if err != nil {
        t.Fatalf("open db: %v", err)
    }
    t.Cleanup(func() { db.Close() })  // runs after test, even on failure
    return db
}
```

### Benchmarks and fuzz tests

```go
func BenchmarkProcess(b *testing.B) {
    data := generateData()
    b.ResetTimer()  // exclude setup time
    for i := 0; i < b.N; i++ {
        Process(data)
    }
}

// Run: go test -bench=. -benchmem

func FuzzParse(f *testing.F) {
    f.Add("valid input")  // seed corpus
    f.Fuzz(func(t *testing.T, s string) {
        _, err := Parse(s)
        // must not panic — error is fine
        _ = err
    })
}
// Run: go test -fuzz=FuzzParse
```

---

## Package and Module Conventions

| Pattern | Rule |
|---|---|
| Package names | Short, lowercase, no underscores: `store`, `auth`, `httputil` |
| Exported names | Self-documenting without package prefix: `store.User` not `store.StoreUser` |
| `internal/` | Enforces package privacy — only importable by parent module |
| `cmd/` | One sub-package per binary entry point |
| Error variables | Prefix with `Err`: `var ErrNotFound = errors.New(...)` |
| Interface location | Define interfaces in the **consumer** package, not the implementer |
| `init()` | Avoid — prefer explicit initialization in `main` or constructors |

```
myapp/
├── cmd/
│   └── server/main.go      # entry point
├── internal/
│   ├── auth/               # private to this module
│   └── store/
├── pkg/                    # reusable, importable by others
│   └── httputil/
└── go.mod
```

---

## Common Gotchas

```go
// Loop variable capture (Go < 1.22) — goroutine closes over the same variable
for _, v := range items {
    go func() { process(v) }()  // BAD pre-1.22: all goroutines see the final v
    go func(v Item) { process(v) }(v)  // GOOD: pass as argument
}
// Go 1.22+: each iteration gets its own copy automatically

// Nil interface != nil pointer
var p *MyType = nil
var i interface{} = p
i == nil  // false — interface has type info even if value is nil
// Return a plain nil to get a nil interface:
func getError() error { return nil }  // not return (*MyError)(nil)

// Slice append aliasing
a := []int{1, 2, 3}
b := a[:2]
b = append(b, 99)  // may overwrite a[2] if cap allows
// Use a[low:high:max] to control capacity and prevent aliasing:
b = a[:2:2]        // cap=2, so append always allocates a new backing array

// Map zero value is nil — must initialize before writing
var m map[string]int
m["x"] = 1  // panic: assignment to entry in nil map
m = make(map[string]int)
m["x"] = 1  // ok

// defer in a loop — deferred until function returns, not loop iteration
for _, f := range files {
    f, _ := os.Open(f)
    defer f.Close()  // BAD: all closes happen at function end
}
// GOOD: wrap in a closure or helper function
for _, name := range files {
    func() {
        f, _ := os.Open(name)
        defer f.Close()
        process(f)
    }()
}
```

---

## Performance Tips

| Technique | When to use |
|---|---|
| Pre-allocate slices | `make([]T, 0, knownLen)` — avoids repeated reallocation |
| Pre-allocate maps | `make(map[K]V, knownLen)` — reduces rehashing |
| `strings.Builder` | Building strings in a loop — never `+=` in a loop |
| `sync.Pool` | Reuse short-lived allocations (buffers, scratch objects) |
| Avoid interface{} in hot paths | Boxing/unboxing costs allocation; use generics or concrete types |
| `//go:noescape` / `unsafe` | Only after profiling with `pprof` |
| Benchmark first | `go test -bench=. -benchmem -cpuprofile=cpu.out` |

---

## Red Flags

- **Goroutine without a stop condition** — every goroutine must have a way to exit (context cancellation, channel close, or done signal); goroutine leaks accumulate and crash servers under load
- **Storing `context.Context` in a struct** — context is request-scoped and must be passed as the first function parameter; storing it bypasses cancellation and makes the struct un-testable
- **`errors.New` compared with `==`** — sentinel errors must use `errors.Is` because wrapping breaks `==`; define `var ErrX = errors.New(...)` and always check with `errors.Is`
- **Shadowing `err` with `:=` in nested scope** — `if err := ...; err != nil` inside a block creates a new `err` that shadows the outer one; outer error is silently unchanged
- **Nil pointer returned as non-nil interface** — returning `(*ConcreteType)(nil)` as an `error` or `interface{}` produces a non-nil interface; always return untyped `nil`
- **`defer` inside a loop** — deferred calls run at function return, not loop end; open file handles accumulate; wrap the loop body in a closure or helper function
- **Fat interfaces defined in the implementer package** — interfaces belong in the consumer package; large interfaces make mocking painful and couple packages unnecessarily
- **Accessing a nil map** — reading is safe (returns zero value), writing panics; always initialize maps with `make`

## Checklist

- [ ] Every `error` return is either handled or explicitly propagated with `fmt.Errorf("...: %w", err)`
- [ ] Sentinel errors use `errors.Is` / `errors.As`, never `==`
- [ ] Every goroutine has a documented exit path (context, channel close, done signal)
- [ ] `context.Context` is the first parameter of every function that does I/O or calls other services
- [ ] `cancel()` from `WithTimeout` / `WithCancel` is deferred immediately after creation
- [ ] Interfaces are defined in the consumer package and kept small (1-3 methods)
- [ ] `sync.WaitGroup.Add()` is called before launching the goroutine, not inside it
- [ ] Slices passed to goroutines are copied or ownership is clearly transferred
- [ ] Maps are initialized with `make` before any write
- [ ] Table-driven tests cover happy path, zero value, and at least one error case
- [ ] Benchmarks use `b.ResetTimer()` after setup and `b.ReportAllocs()`
- [ ] `t.Helper()` is called in every test helper function
