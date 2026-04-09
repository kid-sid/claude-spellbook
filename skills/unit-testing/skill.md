---
name: unit-testing
description: "Unit testing patterns: test structure (Arrange/Act/Assert), mocking and stubbing, parameterized tests, TDD workflow, coverage strategy, and test organization. Examples in pytest, Jest/Vitest, and Go's testing package."
---

# Unit Testing

Structured guidance for writing reliable, maintainable unit tests — covering test anatomy, mocking strategies, parameterized tests, TDD workflow, coverage strategy, and test organization across Python, TypeScript, and Go.

## When to Activate

- Writing tests for a function, class, or module
- Setting up a test framework for a new project
- Mocking or stubbing external dependencies in tests
- Deciding what to unit test vs integration test
- Practising TDD (test-driven development) on a new feature
- Achieving or enforcing a coverage target
- Debugging a flaky or unclear test failure

---

## Test Anatomy

### Arrange / Act / Assert (AAA)

Every test has three distinct phases:

- **Arrange** — set up the inputs, dependencies, and state needed for the test
- **Act** — call the unit under test (exactly once)
- **Assert** — verify the outcome matches expectations

One assertion per *logical concern* means each test validates one observable behaviour. Multiple `assert` statements are fine as long as they all verify the same thing (e.g., both fields of a returned object).

### Test Naming

| Language | Convention | Example |
|---|---|---|
| Python | `test_<unit>_<scenario>_<expected_result>` | `test_divide_by_zero_raises_value_error` |
| TypeScript | `describe('Unit') / it('should ...')` | `it('should throw when dividing by zero')` |
| Go | `TestXxx` with `t.Run("SubtestName", ...)` | `TestDivide/ByZero` |

### Well-Structured Test Examples

```python
# Python — pytest
def test_calculate_total_with_discount_returns_reduced_price():
    # Arrange
    cart = Cart(items=[Item(price=100)])
    discount = PercentageDiscount(rate=0.10)

    # Act
    total = calculate_total(cart, discount)

    # Assert
    assert total == 90.0
```

```typescript
// TypeScript — Jest / Vitest
describe('calculateTotal', () => {
  it('should return reduced price when discount is applied', () => {
    // Arrange
    const cart = { items: [{ price: 100 }] };
    const discount = { rate: 0.10 };

    // Act
    const total = calculateTotal(cart, discount);

    // Assert
    expect(total).toBe(90.0);
  });
});
```

```go
// Go — testing package
func TestCalculateTotal_WithDiscount_ReturnsReducedPrice(t *testing.T) {
    // Arrange
    cart := Cart{Items: []Item{{Price: 100}}}
    discount := Discount{Rate: 0.10}

    // Act
    total := CalculateTotal(cart, discount)

    // Assert
    if total != 90.0 {
        t.Errorf("expected 90.0, got %f", total)
    }
}
```

---

## What to Unit Test

### Decision Table

| Test This | Don't Test This |
|---|---|
| Public functions and methods | Private implementation details |
| Business logic and domain rules | Framework internals (ORM, router) |
| Edge cases: nil/None/null, empty collections | Trivial getters and setters |
| Boundary values (off-by-one, max/min) | Auto-generated code (protobuf, ORM models) |
| Error paths and exception handling | Configuration loading (use integration tests) |
| Conditional branches | `main()` entrypoints |
| Data transformations and calculations | Third-party library behaviour |

### Principles

Test public interfaces. If you must reach into private methods to test behaviour, that is a signal the logic should be extracted into its own testable unit.

Test edge cases explicitly. The most common bugs live at the boundaries:

```python
# BAD — only tests the happy path
def test_get_first_item():
    result = get_first([1, 2, 3])
    assert result == 1

# GOOD — also tests the edge case
def test_get_first_item_returns_none_for_empty_list():
    result = get_first([])
    assert result is None
```

Test error paths. If your function raises, throws, or returns an error value, test that explicitly:

```typescript
// TypeScript
it('should throw InvalidInputError when name is empty', () => {
  expect(() => createUser({ name: '' })).toThrow(InvalidInputError);
});
```

```go
// Go
func TestCreateUser_EmptyName_ReturnsError(t *testing.T) {
    _, err := CreateUser(UserInput{Name: ""})
    if err == nil {
        t.Fatal("expected error for empty name, got nil")
    }
}
```

---

## Mocking, Stubbing, and Spying

### Terminology

| Term | Definition | Use When |
|---|---|---|
| **Stub** | Returns a fixed value; does not record calls | Replacing a dependency that returns data |
| **Mock** | Records calls; assertions on how it was used | Verifying a side-effect was triggered |
| **Spy** | Wraps real implementation; records calls | Checking interactions without replacing logic |
| **Fake** | Lightweight working implementation (e.g., in-memory DB) | Stateful dependencies like repositories |

### Python — `unittest.mock` and `pytest-mock`

```python
from unittest.mock import MagicMock, patch
import pytest

# Stub with MagicMock
def test_send_welcome_email_calls_mailer():
    mailer = MagicMock()
    service = UserService(mailer=mailer)

    service.register(email="user@example.com")

    # Mock assertion — verify interaction
    mailer.send.assert_called_once_with(
        to="user@example.com",
        subject="Welcome"
    )

# Patch with pytest-mock
def test_get_current_time_uses_utcnow(mocker):
    mock_now = mocker.patch("mymodule.datetime")
    mock_now.utcnow.return_value = datetime(2024, 1, 1)

    result = get_current_time()

    assert result == datetime(2024, 1, 1)
```

### TypeScript — Jest and Vitest

```typescript
// jest.fn() — stub / mock
const mockSend = jest.fn().mockResolvedValue({ status: 200 });
const mailer = { send: mockSend };
const service = new UserService(mailer);

await service.register('user@example.com');

expect(mockSend).toHaveBeenCalledWith({
  to: 'user@example.com',
  subject: 'Welcome',
});

// jest.spyOn() — spy on real method
const spy = jest.spyOn(console, 'warn').mockImplementation(() => {});
triggerDeprecatedFeature();
expect(spy).toHaveBeenCalledTimes(1);
spy.mockRestore();

// Vitest equivalents (same API)
import { vi } from 'vitest';
const mockFn = vi.fn();
const spyFn = vi.spyOn(obj, 'method');
```

### Go — Interface-Based Mocking

Go's idiomatic approach is to define an interface for the dependency and provide a test struct that implements it.

```go
// Production interface
type Mailer interface {
    Send(to, subject string) error
}

// Test double — implement the interface manually
type MockMailer struct {
    CalledWith []struct{ To, Subject string }
}

func (m *MockMailer) Send(to, subject string) error {
    m.CalledWith = append(m.CalledWith, struct{ To, Subject string }{to, subject})
    return nil
}

// Test
func TestUserService_Register_SendsWelcomeEmail(t *testing.T) {
    mailer := &MockMailer{}
    svc := NewUserService(mailer)

    svc.Register("user@example.com")

    if len(mailer.CalledWith) != 1 {
        t.Fatalf("expected 1 call, got %d", len(mailer.CalledWith))
    }
    if mailer.CalledWith[0].To != "user@example.com" {
        t.Errorf("unexpected recipient: %s", mailer.CalledWith[0].To)
    }
}
```

### When Mocking Is a Design Smell

If every test requires five mocks to run a single function, the function has too many dependencies. Excessive mocking signals tight coupling — consider refactoring toward pure functions, dependency injection, or smaller units.

```python
# BAD — mocking the system under test
def test_process_order():
    order_service = MagicMock()          # mocking the thing being tested
    order_service.process.return_value = True
    assert order_service.process(order) is True  # tests nothing real

# GOOD — mock only the external boundary
def test_process_order_persists_to_repository():
    repo = MagicMock()
    service = OrderService(repo=repo)    # inject the dependency
    service.process(order)
    repo.save.assert_called_once_with(order)
```

---

## Parameterized Tests

Use parameterized tests when the same logic needs to be verified against many input/output pairs. This avoids copy-pasting test bodies and makes the full test matrix visible at a glance.

### Example: `validate_email()` across 5 cases

```python
# Python — pytest.mark.parametrize with IDs
import pytest

@pytest.mark.parametrize("email,expected", [
    ("user@example.com",   True),
    ("USER@EXAMPLE.COM",   True),
    ("missing-at-sign",    False),
    ("@nodomain.com",      False),
    ("",                   False),
], ids=[
    "valid_standard",
    "valid_uppercase",
    "invalid_no_at",
    "invalid_no_local_part",
    "invalid_empty",
])
def test_validate_email(email, expected):
    assert validate_email(email) == expected
```

```typescript
// TypeScript — Jest test.each / Vitest it.each
describe('validateEmail', () => {
  it.each([
    ['user@example.com',  true,  'valid standard'],
    ['USER@EXAMPLE.COM',  true,  'valid uppercase'],
    ['missing-at-sign',   false, 'invalid no at'],
    ['@nodomain.com',     false, 'invalid no local part'],
    ['',                  false, 'invalid empty'],
  ])('should return %s for "%s" (%s)', (email, expected) => {
    expect(validateEmail(email)).toBe(expected);
  });
});
```

```go
// Go — table-driven tests with t.Run
func TestValidateEmail(t *testing.T) {
    cases := []struct {
        name     string
        email    string
        expected bool
    }{
        {"valid standard",        "user@example.com", true},
        {"valid uppercase",       "USER@EXAMPLE.COM", true},
        {"invalid no at",         "missing-at-sign",  false},
        {"invalid no local part", "@nodomain.com",    false},
        {"invalid empty",         "",                 false},
    }

    for _, tc := range cases {
        t.Run(tc.name, func(t *testing.T) {
            result := ValidateEmail(tc.email)
            if result != tc.expected {
                t.Errorf("ValidateEmail(%q): got %v, want %v", tc.email, result, tc.expected)
            }
        })
    }
}
```

---

## Test Doubles for External I/O

### Fakes vs Mocks

| Approach | Best For | Example |
|---|---|---|
| **Fake** | Stateful dependencies with real behaviour | In-memory repository |
| **Mock** | Fire-and-forget calls where you verify interaction | Email sender, event bus |
| **HTTP stub** | Outbound HTTP clients | `responses`, `msw`, `httptest` |

Use fakes for repositories and other stateful collaborators — they give you real insert/find behaviour without a live database. Use mocks for fire-and-forget side-effects (emails, queues) where the key assertion is that the call was made at all.

### In-Memory Repository (Fake)

```python
# Python — fake repository for stateful DB calls
class InMemoryUserRepository:
    def __init__(self):
        self._store = {}

    def save(self, user):
        self._store[user.id] = user

    def find_by_id(self, user_id):
        return self._store.get(user_id)
```

```typescript
// TypeScript — fake repository
class InMemoryUserRepository implements UserRepository {
  private store = new Map<string, User>();

  async save(user: User): Promise<void> {
    this.store.set(user.id, user);
  }

  async findById(id: string): Promise<User | undefined> {
    return this.store.get(id);
  }
}
```

```go
// Go — fake repository struct
type InMemoryUserRepo struct {
    store map[string]User
}

func NewInMemoryUserRepo() *InMemoryUserRepo {
    return &InMemoryUserRepo{store: make(map[string]User)}
}

func (r *InMemoryUserRepo) Save(u User) error {
    r.store[u.ID] = u
    return nil
}

func (r *InMemoryUserRepo) FindByID(id string) (User, bool) {
    u, ok := r.store[id]
    return u, ok
}
```

### Mocking HTTP Clients

```python
# Python — responses library
import responses as rsps
import requests

@rsps.activate
def test_fetch_user_returns_parsed_data():
    rsps.add(rsps.GET, "https://api.example.com/users/1",
             json={"id": 1, "name": "Alice"}, status=200)

    user = fetch_user(1)

    assert user.name == "Alice"
```

```typescript
// TypeScript — msw (Mock Service Worker)
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

const server = setupServer(
  http.get('https://api.example.com/users/:id', () =>
    HttpResponse.json({ id: 1, name: 'Alice' })
  )
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

it('should return parsed user data', async () => {
  const user = await fetchUser(1);
  expect(user.name).toBe('Alice');
});
```

```go
// Go — httptest.NewServer
func TestFetchUser_ReturnsUser(t *testing.T) {
    server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Content-Type", "application/json")
        fmt.Fprintln(w, `{"id":1,"name":"Alice"}`)
    }))
    defer server.Close()

    client := NewAPIClient(server.URL)
    user, err := client.FetchUser(1)

    if err != nil {
        t.Fatal(err)
    }
    if user.Name != "Alice" {
        t.Errorf("expected Alice, got %s", user.Name)
    }
}
```

---

## TDD Workflow

### Red → Green → Refactor

- **Red** — write a failing test that specifies the behaviour you want before writing any implementation
- **Green** — write the minimum code required to make the test pass, even if the code is ugly
- **Refactor** — clean up duplication and improve design with the safety net of a passing test

### When TDD Pays Off

| Situation | TDD Value |
|---|---|
| New feature with clear acceptance criteria | High |
| Complex business logic (pricing, validation, state machines) | High |
| Regression prevention on a known bug | High |
| Exploratory / spike code | Low — write tests after the design emerges |
| UI layout and visual components | Low — prefer visual regression tools |
| Third-party integration spike | Low — integration tests are more appropriate |

### Outside-In TDD

Start from the outer boundary (e.g., an HTTP handler or a use case) and write a failing acceptance test. Mock all inner collaborators. Then drive out each collaborator with its own unit tests, working inward until all mocks are replaced by real implementations.

---

## Coverage Strategy

### What Each Metric Measures

| Metric | Measures | Limitation |
|---|---|---|
| **Line coverage** | Whether each line was executed | A line can be hit without testing all outcomes |
| **Branch coverage** | Whether each `if`/`else` path was taken | Misses logic errors in the execution path |
| **Mutation testing** | Whether tests detect small code changes | Slow; use on critical modules only |

### Realistic Targets

| Context | Line Coverage | Branch Coverage |
|---|---|---|
| Greenfield project | 80%+ | 70%+ |
| Existing codebase | Raise incrementally by 5% per sprint | Focus on new code |
| Critical path (payments, auth, core domain) | 95%+ | 90%+ |
| Generated or migration code | Exclude | Exclude |

### What to Exclude from Coverage

- Database migration files
- Auto-generated code (protobuf, ORM schema)
- `main()` entrypoints and CLI bootstrap
- Configuration loaders and environment readers
- Third-party adapter shims

### Tools

```python
# Python — pytest-cov
pytest --cov=src --cov-report=term-missing --cov-branch
```

```typescript
// TypeScript — Jest
// jest.config.ts
export default {
  collectCoverage: true,
  coverageThreshold: { global: { lines: 80, branches: 70 } },
  coveragePathIgnorePatterns: ['/generated/', '/migrations/'],
};

// Vitest — vitest.config.ts
export default defineConfig({
  test: {
    coverage: { provider: 'v8', thresholds: { lines: 80, branches: 70 } },
  },
});
```

```bash
# Go
go test ./... -cover -coverprofile=coverage.out
go tool cover -html=coverage.out
```

Coverage is a floor, not a goal. 100% line coverage achieved by testing only the happy path with no meaningful assertions is worse than 70% coverage with rigorous, well-structured tests.

---

## Test Organization

### Co-location vs Separate Directory

| Language | Convention | Notes |
|---|---|---|
| Python | `tests/` at project root | Mirrors `src/` structure; `conftest.py` for shared fixtures |
| TypeScript | `*.test.ts` or `*.spec.ts` co-located, or `__tests__/` folder | Co-location is most common in React/Node projects |
| Go | `_test.go` suffix, same directory as source | Same package = white-box; `package foo_test` suffix = black-box |

### Python: `conftest.py` and Fixtures

```python
# tests/conftest.py — shared fixtures available to all tests
import pytest
from myapp.db import Database

@pytest.fixture
def db():
    database = Database(url="sqlite:///:memory:")
    database.create_tables()
    yield database
    database.drop_tables()

@pytest.fixture
def user_repo(db):
    return UserRepository(db)
```

### Go: White-Box vs Black-Box Tests

```go
// white_box_test.go — same package, can access unexported identifiers
package cart

func TestInternalDiscount(t *testing.T) {
    d := applyInternalDiscount(100, 0.10) // unexported function
    if d != 90.0 {
        t.Errorf("expected 90.0, got %f", d)
    }
}

// black_box_test.go — _test package suffix, only public API visible
package cart_test

func TestCart_AddItem(t *testing.T) {
    c := cart.New()
    c.Add(cart.Item{Price: 50})
    if c.Total() != 50 {
        t.Errorf("expected total 50, got %f", c.Total())
    }
}
```

### Test Isolation

```python
# BAD — shared mutable state between tests
_global_cache = {}

def test_a():
    _global_cache["key"] = "value"

def test_b():
    assert _global_cache.get("key") is None  # fails if test_a ran first

# GOOD — each test owns its state
def test_b():
    cache = {}
    result = process_with_cache(cache, "key")
    assert result is not None
```

Clean up after each test. Use `setUp`/`tearDown`, pytest fixtures with `yield`, Jest's `beforeEach`/`afterEach`, or Go's `t.Cleanup()` to reset shared resources.

### Parallel Test Execution

| Tool | Parallel Flag | Notes |
|---|---|---|
| pytest | `pytest-xdist`: `pytest -n auto` | Tests must be stateless; use `tmp_path` fixture for filesystem |
| Jest | `--maxWorkers=4` (parallel) or `--runInBand` (serial) | Use `--runInBand` when tests share a real database |
| Vitest | `pool: 'threads'` (default) or `pool: 'forks'` | Configure in `vitest.config.ts` |
| Go | `t.Parallel()` inside each test | Call at the top of the test function; subtests inherit the pool |

```go
func TestCalculate(t *testing.T) {
    t.Parallel() // opt in to parallel execution

    t.Run("adds correctly", func(t *testing.T) {
        t.Parallel()
        result := Add(2, 3)
        if result != 5 {
            t.Errorf("expected 5, got %d", result)
        }
    })
}
```

---

## Checklist

- [ ] Tests follow AAA pattern with clear arrange/act/assert separation
- [ ] Test names describe the scenario and expected outcome
- [ ] Each test has a single logical assertion (one behaviour per test)
- [ ] External dependencies (DB, HTTP, filesystem) are mocked or faked
- [ ] Edge cases covered: null/None/nil, empty collections, boundary values, error paths
- [ ] Parameterized tests used for multiple input/output scenarios of the same logic
- [ ] No test relies on execution order or shared mutable state
- [ ] Coverage meets project threshold for both line and branch coverage
- [ ] Flaky tests are quarantined or fixed before merging to main
- [ ] Test suite runs in under 60 seconds locally
- [ ] Public interfaces are tested, not private implementation details
- [ ] Mocks are only used for external boundaries, not for the unit under test
- [ ] Fixtures and fakes are cleaned up after each test (no state leakage)
- [ ] TDD red/green/refactor cycle followed for new business logic
- [ ] Generated, migration, and configuration code is excluded from coverage requirements
