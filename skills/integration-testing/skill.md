---
name: integration-testing
description: "Integration testing patterns: Testcontainers for real database/broker tests, HTTP API testing at service level, consumer-driven contract testing with Pact, message queue testing, and test data management. Examples in Python, TypeScript, and Go."
---

# Integration Testing

Integration tests verify that components work correctly together — real databases, real HTTP routing, real serialization — catching the bugs that unit tests cannot.

## When to Activate

- Testing code that reads from or writes to a real database
- Testing an HTTP endpoint end-to-end within the service boundary
- Setting up Testcontainers for a project
- Writing contract tests between two services
- Testing event-driven or message queue workflows
- Managing test fixtures, factories, and teardown strategies
- Diagnosing tests that pass in isolation but fail in CI

---

## Integration vs Unit: The Boundary

Integration tests add real I/O, real wiring, and real serialization. They catch mismatches between your code and the actual database schema, ORM behavior, HTTP middleware ordering, and message envelope formats. What they cost: seconds instead of milliseconds, a Docker dependency, and a higher flakiness risk if not isolated properly.

**Testing pyramid starting point:** 70% unit / 20% integration / 10% E2E.

| Situation | Use unit test | Use integration test |
|---|---|---|
| Pure function, no I/O | Yes | No |
| DB query logic | Mock is fine for query shape | Yes — real DB for index, constraint, join behavior |
| HTTP handler | Mock dependencies to test logic | Yes — real router for middleware, serialization |
| External API call | Mock HTTP client | Yes — use recorded fixtures or contract test |
| Message handler | Mock broker for handler logic | Yes — real broker for publish/consume wiring |
| Validation rules | Yes — fast feedback | No — unless schema is DB-enforced |

---

## Database Integration Tests with Testcontainers

Testcontainers spins up a real Docker container (Postgres, MySQL, Redis, Kafka, etc.) per test suite, giving every developer and CI run an identical, isolated database. No shared test databases, no "works on my machine."

### Python

```python
# pip install testcontainers[postgres] psycopg2-binary pytest sqlalchemy

import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine, text

@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg

@pytest.fixture(scope="session")
def engine(postgres):
    engine = create_engine(postgres.get_connection_url())
    # Run migrations before the suite
    # alembic.config.main(argv=["upgrade", "head"])
    return engine

@pytest.fixture
def db(engine):
    # BAD: commit data and delete after — leaves residue if test crashes
    # conn.execute(text("DELETE FROM users WHERE id = :id"), ...)
    # GOOD: wrap in a transaction and roll back — zero cleanup needed
    with engine.begin() as conn:
        savepoint = conn.begin_nested()
        yield conn
        savepoint.rollback()
```

### TypeScript

```typescript
// npm install testcontainers pg @types/pg

import { PostgreSqlContainer, StartedPostgreSqlContainer } from "testcontainers";
import { Pool } from "pg";
import { runMigrations } from "../db/migrate";

let container: StartedPostgreSqlContainer;
let pool: Pool;

beforeAll(async () => {
  container = await new PostgreSqlContainer("postgres:16").start();
  pool = new Pool({ connectionString: container.getConnectionUri() });
  await runMigrations(pool); // run prisma migrate / knex migrate:latest
}, 60_000);

afterAll(async () => {
  await pool.end();
  await container.stop();
});

beforeEach(async () => {
  await pool.query("BEGIN");
});

afterEach(async () => {
  // GOOD: rollback keeps tests hermetic
  await pool.query("ROLLBACK");
});
```

### Go

```go
// go get github.com/testcontainers/testcontainers-go/modules/postgres

package db_test

import (
    "context"
    "testing"

    tcpostgres "github.com/testcontainers/testcontainers-go/modules/postgres"
    "github.com/testcontainers/testcontainers-go/wait"
)

func TestMain(m *testing.M) {
    ctx := context.Background()
    container, err := tcpostgres.RunContainer(ctx,
        tcpostgres.WithDatabase("testdb"),
        tcpostgres.WithUsername("test"),
        tcpostgres.WithPassword("test"),
        tcpostgres.WithInitScripts("schema.sql"),
        testcontainers.WithWaitStrategy(
            wait.ForLog("database system is ready to accept connections"),
        ),
    )
    if err != nil {
        panic(err)
    }
    defer container.Terminate(ctx)

    connStr, _ := container.ConnectionString(ctx, "sslmode=disable")
    // pass connStr to your repository layer
    m.Run()
}
```

### Fixture Factories

Build test objects with a factory: sensible defaults, every field overridable.

```python
# Python — factory_boy
import factory
from myapp.models import User

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    name = "Test User"
    role = "member"
    is_active = True

# In a test:
admin = UserFactory(role="admin")
inactive = UserFactory(is_active=False)
```

```typescript
// TypeScript — plain builder
function buildUser(overrides: Partial<User> = {}): User {
  return {
    id: crypto.randomUUID(),
    email: `user-${Date.now()}@example.com`,
    name: "Test User",
    role: "member",
    isActive: true,
    ...overrides,
  };
}

const admin = buildUser({ role: "admin" });
```

```go
// Go — functional options
func NewUser(opts ...func(*User)) User {
    u := User{
        ID:       uuid.New(),
        Email:    fmt.Sprintf("user-%d@example.com", time.Now().UnixNano()),
        Name:     "Test User",
        Role:     "member",
        IsActive: true,
    }
    for _, opt := range opts {
        opt(&u)
    }
    return u
}

func WithRole(role string) func(*User) {
    return func(u *User) { u.Role = role }
}

admin := NewUser(WithRole("admin"))
```

### Schema Migrations Before Suite

Always run migrations against the container before tests run — never against a pre-seeded snapshot.

- **Python/Alembic:** `alembic upgrade head` pointed at the container URL
- **TypeScript/Prisma:** `prisma migrate deploy` with `DATABASE_URL` set to container URL
- **Go/golang-migrate:** `migrate -path ./migrations -database $DSN up`

---

## HTTP API Testing at the Service Level

Test the full request/response cycle — routing, middleware, validation, serialization — without going over the network. The goal is to exercise real handler wiring, not mocked HTTP.

### Python (FastAPI / Starlette)

```python
# pip install httpx pytest

from fastapi.testclient import TestClient
from myapp.main import app

client = TestClient(app)

def test_user_lifecycle(db):  # db fixture provides rolled-back session
    # Create
    resp = client.post("/users", json={"email": "a@example.com", "name": "Alice"})
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    # Read back
    resp = client.get(f"/users/{user_id}")
    assert resp.status_code == 200
    assert resp.json()["email"] == "a@example.com"

    # Delete
    resp = client.delete(f"/users/{user_id}")
    assert resp.status_code == 204

    resp = client.get(f"/users/{user_id}")
    assert resp.status_code == 404
```

### TypeScript (Express / Fastify)

```typescript
// npm install supertest @types/supertest

import request from "supertest";
import { buildApp } from "../src/app";

const app = buildApp({ db: testPool });

test("user lifecycle", async () => {
  const create = await request(app)
    .post("/users")
    .send({ email: "a@example.com", name: "Alice" })
    .expect(201);

  const { id } = create.body;

  await request(app).get(`/users/${id}`).expect(200).expect((res) => {
    expect(res.body.email).toBe("a@example.com");
  });

  await request(app).delete(`/users/${id}`).expect(204);
  await request(app).get(`/users/${id}`).expect(404);
});
```

### Go

```go
import (
    "net/http"
    "net/http/httptest"
    "testing"
    "bytes"
    "encoding/json"
)

func TestUserLifecycle(t *testing.T) {
    handler := buildRouter(testDB)

    // Create
    body, _ := json.Marshal(map[string]string{"email": "a@example.com", "name": "Alice"})
    w := httptest.NewRecorder()
    handler.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/users", bytes.NewReader(body)))
    if w.Code != http.StatusCreated { t.Fatalf("expected 201, got %d", w.Code) }

    var created map[string]any
    json.NewDecoder(w.Body).Decode(&created)
    id := created["id"].(string)

    // Read back
    w = httptest.NewRecorder()
    handler.ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/users/"+id, nil))
    if w.Code != http.StatusOK { t.Fatalf("expected 200, got %d", w.Code) }

    // Delete
    w = httptest.NewRecorder()
    handler.ServeHTTP(w, httptest.NewRequest(http.MethodDelete, "/users/"+id, nil))
    if w.Code != http.StatusNoContent { t.Fatalf("expected 204, got %d", w.Code) }
}
```

### Auth in Integration Tests

Injecting real tokens makes tests slow and fragile. Instead:

```python
# BAD
token = requests.post("/auth/login", json={"password": "..."}).json()["token"]
client.headers["Authorization"] = f"Bearer {token}"

# GOOD — test config bypasses auth middleware, or inject a pre-signed token
client = TestClient(app, headers={"X-Test-User-Id": str(user.id)})
# Middleware reads X-Test-User-Id only when TEST_MODE=true
```

---

## Contract Testing with Pact

Consumer-driven contract testing lets two services independently verify the API shape they agree on, without running both services simultaneously.

**Consumer side:** The consumer writes a Pact — a description of the interactions it expects. Pact runs a mock provider to record the contract.

**Provider side:** The provider fetches the Pact from the Pact Broker and replays each interaction against its real implementation.

**Pact Broker:** A shared registry where consumers publish contracts and providers pull them. Teams can see which consumers depend on which provider endpoints.

```python
# Consumer (Python pact-python)
from pact import Consumer, Provider

pact = Consumer("OrderService").has_pact_with(Provider("UserService"))

pact.given("user 42 exists").upon_receiving("a request for user 42").with_request(
    "GET", "/users/42"
).will_respond_with(200, body={"id": 42, "name": Like("Alice")})

with pact:
    # call your actual client code against pact.uri
    user = get_user(42, base_url=pact.uri)
    assert user["id"] == 42
```

```typescript
// Consumer (TypeScript pact-js)
import { PactV3, MatchersV3 } from "@pact-foundation/pact";

const provider = new PactV3({ consumer: "OrderService", provider: "UserService" });

provider
  .given("user 42 exists")
  .uponReceiving("a request for user 42")
  .withRequest({ method: "GET", path: "/users/42" })
  .willRespondWith({
    status: 200,
    body: { id: MatchersV3.integer(42), name: MatchersV3.string("Alice") },
  });

await provider.executeTest(async (mockServer) => {
  const user = await getUser(42, mockServer.url);
  expect(user.id).toBe(42);
});
```

### When to Use / When Not to Use Pact

| Scenario | Use Pact | Skip Pact |
|---|---|---|
| Microservices, different teams | Yes | — |
| Consumer and provider deploy independently | Yes | — |
| Monolith with internal module calls | No | Unit/integration test |
| Same team owns both services | Optional — adds overhead | — |
| Internal library (not HTTP) | No | Unit test |
| Third-party external API | Use recorded fixtures instead | — |

---

## Message Queue and Event Testing

### Testing Producers

Capture published messages in a list and assert on payload shape and schema.

```python
# Python — fake Redis pub/sub with fakeredis
import fakeredis
from myapp.events import publish_order_created

def test_publish_order_created():
    r = fakeredis.FakeRedis()
    pubsub = r.pubsub()
    pubsub.subscribe("orders")

    publish_order_created(r, order_id="abc-123", amount=99.99)

    message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
    payload = json.loads(message["data"])
    assert payload["order_id"] == "abc-123"
    assert payload["event"] == "order.created"
```

```typescript
// TypeScript — capture calls with a fake queue
const published: unknown[] = [];
const fakeQueue = {
  add: (name: string, data: unknown) => {
    published.push({ name, data });
    return Promise.resolve();
  },
};

await handleCheckout(fakeQueue, { orderId: "abc-123", amount: 99.99 });

expect(published).toHaveLength(1);
expect((published[0] as any).name).toBe("order.created");
expect((published[0] as any).data.orderId).toBe("abc-123");
```

```go
// Go — channel-based fake
type FakePublisher struct {
    Messages []Event
}

func (f *FakePublisher) Publish(ctx context.Context, e Event) error {
    f.Messages = append(f.Messages, e)
    return nil
}

func TestPublishOrderCreated(t *testing.T) {
    pub := &FakePublisher{}
    HandleCheckout(pub, Order{ID: "abc-123", Amount: 99.99})
    if len(pub.Messages) != 1 { t.Fatal("expected 1 message") }
    if pub.Messages[0].Type != "order.created" { t.Fatal("wrong event type") }
}
```

### Testing Consumers

Inject a raw message into the handler and assert on side effects (DB row created, email sent, etc.).

```python
# Python — Celery with CELERY_TASK_ALWAYS_EAGER
@pytest.fixture(autouse=True)
def eager_celery(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True

def test_consumer_creates_order(db):
    send_order_created.delay({"order_id": "abc-123", "amount": 99.99})
    order = db.query(Order).filter_by(id="abc-123").one()
    assert order.amount == Decimal("99.99")
```

---

## Test Data Management

### Factory Pattern

A factory builds valid domain objects with sensible defaults. Every field is overridable. Never write raw SQL inserts in test bodies.

```python
# BAD
cursor.execute("INSERT INTO users (id, email, role) VALUES ('1', 'a@b.com', 'member')")

# GOOD
user = UserFactory(role="admin")
```

### Seeders vs Per-Test Factories

| Data type | Strategy |
|---|---|
| Reference data (countries, roles, plans) | Seeder — run once per suite |
| Test-specific domain objects | Factory — per test, rolled back |
| Large static lookup tables | Seeder — loaded from fixture file |
| Data with relationships under test | Factory — build full object graph |

### Cleanup Strategies

| Strategy | When to use | Notes |
|---|---|---|
| Transaction rollback | Most cases | Fastest; requires single connection per test |
| Truncate after suite | Parallel workers with separate schemas | Slower than rollback |
| Test-specific schema | Parallel workers on shared DB | Drop schema after worker finishes |
| Delete by test ID | Legacy codebases only | Fragile — skip if possible |

### Snapshot Testing

Serialize a complex object to a file; fail if it changes. Useful for stable API response shapes.

```python
# Python — syrupy
def test_user_response_shape(snapshot, client):
    resp = client.get("/users/1")
    assert resp.json() == snapshot  # creates __snapshots__/test_users.ambr on first run
```

```typescript
// TypeScript — jest --updateSnapshot
test("user response shape", async () => {
  const resp = await request(app).get("/users/1").expect(200);
  expect(resp.body).toMatchSnapshot();
});
```

---

## Test Environment Isolation

Never share a test database URL with development or production. Keep a separate `.env.test` (or `config/test.yaml`) that is committed to the repo but contains only non-sensitive test-specific values.

```bash
# .env.test — committed, non-sensitive
DATABASE_URL=postgres://test:test@localhost:5433/apptest
REDIS_URL=redis://localhost:6380/1
MESSAGE_BROKER_URL=amqp://guest:guest@localhost:5673/
```

### Schema-per-Test vs Separate DB per Worker

| Approach | Speed | Isolation | Use when |
|---|---|---|---|
| Transaction rollback, shared schema | Fastest | Strong (single connection) | Default for most suites |
| Schema-per-worker (`search_path`) | Fast | Good | Parallel pytest-xdist workers |
| Separate DB per worker | Slow to create | Strongest | Long parallel suites with DDL |

### Parallel Test Safety

```python
# BAD — two workers both insert user with email "admin@example.com"
user = UserFactory(email="admin@example.com")

# GOOD — unique per worker run
user = UserFactory(email=f"admin-{uuid.uuid4()}@example.com")
# Or use factory_boy sequences which are process-local
user = UserFactory()  # email = factory.Sequence(lambda n: f"user{n}@example.com")
```

### CI Considerations

- Ensure the CI runner has a Docker socket available (GitHub Actions `ubuntu-latest` does by default).
- For environments without Docker (some hosted runners, sandboxed CI), use **Testcontainers Cloud** — it offloads container startup to a remote daemon with no local Docker required.
- Cache container images in CI to reduce startup latency (`docker pull postgres:16` as a warm-up step or via registry mirror).
- Set `TESTCONTAINERS_RYUK_DISABLED=true` only if your CI runner cannot start the Ryuk reaper container (rootless Docker environments).

---

## Checklist

- [ ] Integration tests use a real database/broker (no mocked I/O at the storage layer)
- [ ] Testcontainers or equivalent used so tests are reproducible on any machine
- [ ] Each test cleans up after itself (transaction rollback or truncate)
- [ ] HTTP tests exercise real request parsing, validation, and response serialization
- [ ] Test data is created via factories, not hand-crafted raw SQL inserts
- [ ] Contract tests exist at every service boundary with different team ownership
- [ ] Message queue tests verify both publish payload schema and consumer side effects
- [ ] Test environment uses a separate DB from dev — never `DATABASE_URL` from `.env`
- [ ] Parallel test workers are isolated (no shared mutable rows)
- [ ] Integration test suite completes in under 5 minutes in CI
- [ ] Schema migrations run against the test container before the suite starts
- [ ] Snapshot tests exist for complex, stable API response shapes
- [ ] Auth bypassed in tests via test config, not by hard-coding credentials
- [ ] Reference/lookup data loaded via seeders; test-specific data via factories
