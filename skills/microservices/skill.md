---
name: microservices
description: Microservices architecture patterns covering service decomposition, inter-service communication (sync/async), resilience (circuit breaker, saga, bulkhead), data isolation, API gateway, and service mesh for distributed backend systems.
---

# Microservices Patterns

Design and implementation patterns for decomposing monoliths and building reliable distributed backend systems.

## When to Activate

- Decomposing a monolith into services or defining service boundaries
- Choosing between synchronous (REST/gRPC) and asynchronous (messaging) communication
- Implementing resilience patterns: circuit breaker, retry, bulkhead, timeout
- Designing data ownership and cross-service transactions (Saga, CQRS)
- Setting up an API gateway or BFF for client-facing traffic
- Designing for eventual consistency or event-driven workflows
- Debugging distributed failures, cascading errors, or data inconsistency

## Service Decomposition

### Decomposition Strategies

| Strategy | Approach | Best For |
|---|---|---|
| By domain (DDD) | Align services to bounded contexts | Greenfield, domain-rich systems |
| By subdomain | Core / supporting / generic subdomains | Prioritising build-vs-buy |
| Strangler fig | Incrementally replace monolith routes | Existing monoliths |
| By volatility | Isolate frequently-changing logic | High-churn business rules |

### Bounded Context Rules

```
# BAD: Shared User model across services
OrderService   → reads User.loyaltyPoints
PaymentService → reads User.billingAddress
EmailService   → reads User.email

# GOOD: Each service owns what it needs
OrderService   → owns OrderCustomer { id, name, loyaltyPoints }
PaymentService → owns PaymentProfile { userId, billingAddress, paymentMethods }
EmailService   → owns ContactRecord { userId, email, preferences }
```

Each service owns its data. No direct cross-service DB queries.

### Strangler Fig Migration

```
1. Route all traffic through a facade (nginx / API gateway)
2. Identify one vertical slice (e.g., /api/payments/*)
3. Implement that slice as a new service
4. Re-route the facade to the new service
5. Delete the monolith code for that slice
6. Repeat — monolith shrinks, services grow
```

## Inter-Service Communication

### Sync vs Async Decision

| Factor | Sync (REST / gRPC) | Async (Queue / Events) |
|---|---|---|
| Latency requirement | Low — caller needs immediate response | Can tolerate delay |
| Coupling | Temporal coupling (both must be up) | Decoupled — producer/consumer independent |
| Use case | Queries, user-facing reads | Commands, workflows, notifications |
| Error handling | Propagates to caller immediately | Dead-letter queue, retry policies |
| Throughput | Limited by slowest service | Buffered; consumer scales independently |

### Sync: REST

```python
# Python — requests with retry and timeout
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def get_user(user_id: str) -> dict:
    response = httpx.get(
        f"http://user-service/users/{user_id}",
        timeout=2.0,  # always set a timeout
    )
    response.raise_for_status()
    return response.json()["data"]
```

```typescript
// TypeScript — fetch with timeout and retry
async function getUser(userId: string): Promise<User> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2000);
  try {
    const res = await fetch(`http://user-service/users/${userId}`, {
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`upstream error: ${res.status}`);
    return (await res.json()).data;
  } finally {
    clearTimeout(timeout);
  }
}
```

```go
// Go — http client with timeout
func (c *UserClient) GetUser(ctx context.Context, userID string) (*User, error) {
    ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
    defer cancel()

    req, _ := http.NewRequestWithContext(ctx, http.MethodGet,
        fmt.Sprintf("http://user-service/users/%s", userID), nil)
    resp, err := c.http.Do(req)
    if err != nil {
        return nil, fmt.Errorf("user-service: %w", err)
    }
    defer resp.Body.Close()
    // decode...
}
```

### Sync: gRPC (preferred for internal service-to-service)

```proto
// order.proto
service OrderService {
  rpc GetOrder (GetOrderRequest) returns (Order);
  rpc CreateOrder (CreateOrderRequest) returns (Order);
  rpc ListOrders (ListOrdersRequest) returns (stream Order);  // server streaming
}

message GetOrderRequest { string order_id = 1; }
message Order {
  string id = 1;
  string customer_id = 2;
  OrderStatus status = 3;
  repeated OrderItem items = 4;
}
```

### Async: Message Broker

```python
# Python — publishing an event (Kafka)
from confluent_kafka import Producer
import json

producer = Producer({"bootstrap.servers": "kafka:9092"})

def publish_order_placed(order: Order):
    event = {
        "event_type": "order.placed",
        "order_id": order.id,
        "customer_id": order.customer_id,
        "total": str(order.total),
        "occurred_at": order.created_at.isoformat(),
    }
    producer.produce(
        topic="orders",
        key=order.id,
        value=json.dumps(event).encode(),
    )
    producer.flush()
```

```typescript
// TypeScript — consuming events (Kafka / KafkaJS)
const consumer = kafka.consumer({ groupId: "notification-service" });
await consumer.subscribe({ topic: "orders", fromBeginning: false });
await consumer.run({
  eachMessage: async ({ message }) => {
    const event = JSON.parse(message.value!.toString());
    if (event.event_type === "order.placed") {
      await notifyCustomer(event.customer_id, event.order_id);
    }
  },
});
```

## Resilience Patterns

### Circuit Breaker

```python
# Python — using pybreaker
import pybreaker

breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=30)

@breaker
def call_inventory_service(product_id: str) -> int:
    return inventory_client.get_stock(product_id)

# States: CLOSED (normal) → OPEN (failing, fast-fail) → HALF-OPEN (probing)
```

```go
// Go — using gobreaker
import "github.com/sony/gobreaker"

cb := gobreaker.NewCircuitBreaker(gobreaker.Settings{
    Name:        "inventory-service",
    MaxRequests: 3,                // requests allowed in half-open
    Interval:    10 * time.Second, // rolling window
    Timeout:     30 * time.Second, // how long to stay OPEN
    ReadyToTrip: func(counts gobreaker.Counts) bool {
        return counts.ConsecutiveFailures > 5
    },
})

stock, err := cb.Execute(func() (interface{}, error) {
    return inventoryClient.GetStock(ctx, productID)
})
```

### Bulkhead

```python
# Isolate thread pools per downstream dependency
from concurrent.futures import ThreadPoolExecutor

_inventory_pool = ThreadPoolExecutor(max_workers=10)  # capped per service
_payment_pool   = ThreadPoolExecutor(max_workers=5)

def get_stock(product_id: str):
    future = _inventory_pool.submit(inventory_client.get_stock, product_id)
    return future.result(timeout=2)
```

### Retry and Backoff

```
# GOOD: exponential backoff with jitter
attempt 1: wait 1s ± 0.5s
attempt 2: wait 2s ± 1s
attempt 3: wait 4s ± 2s
→ stop after 3 attempts, raise to caller

# BAD: retry storm
for i in range(10):
    try: call_service()
    except: continue  # hammers a degraded service
```

## Data Management

### Per-Service Database (Mandatory)

```
# BAD: shared database
OrderService   → SELECT * FROM payments.transactions WHERE order_id = ?
PaymentService → SELECT * FROM orders.orders WHERE user_id = ?

# GOOD: service-owned databases, expose data via API or events
OrderService   → owns orders_db (Postgres)
PaymentService → owns payments_db (Postgres)
InventoryService → owns inventory_db (Redis + Postgres)
```

### Saga Pattern (Distributed Transactions)

Two flavours:

| Type | Mechanism | Use When |
|---|---|---|
| Choreography | Each service emits events that trigger the next | Simple flows, low coupling |
| Orchestration | Central saga orchestrator drives the steps | Complex flows, explicit rollback |

```python
# Choreography saga — order placement
# 1. OrderService publishes order.created
# 2. PaymentService listens → charges card → publishes payment.succeeded or payment.failed
# 3. InventoryService listens to payment.succeeded → reserves stock → publishes stock.reserved
# 4. OrderService listens to stock.reserved → marks order CONFIRMED
# 5. On any failure: compensating events roll back upstream steps

# Compensating transaction example
def on_payment_failed(event):
    order_service.cancel_order(event["order_id"])   # compensation
    notification_service.notify_customer(event["customer_id"], "payment_failed")
```

### CQRS (Command Query Responsibility Segregation)

```
Write path:  POST /orders        → OrderCommandHandler → orders_db (normalized)
                                 → publishes order.placed event

Read path:   GET /orders/:id     → OrderQueryHandler   → orders_read_db (denormalized view)
             GET /orders?user=X  → OrderQueryHandler   → orders_read_db (pre-joined)

Read model updated by: consuming order.placed / order.updated events
```

Use CQRS when read and write models have fundamentally different shapes or scale requirements.

## API Gateway and BFF

### API Gateway Responsibilities

```
Client → API Gateway → [UserService, OrderService, ProductService]

Gateway handles:
  - Authentication (JWT verification)
  - Rate limiting per client / API key
  - Request routing / URL rewriting
  - SSL termination
  - Logging and distributed trace injection (X-Request-ID, traceparent)
  - Response aggregation (optional)
```

### Backend for Frontend (BFF)

```
Mobile App   → Mobile BFF   → [fine-grained internal APIs]
Web App      → Web BFF      → [fine-grained internal APIs]
Partner API  → Partner BFF  → [fine-grained internal APIs]

# Each BFF is thin: aggregate, reshape, and auth-scope data for its client
# BAD: one general-purpose gateway trying to serve all clients equally
```

## Service Discovery

| Method | How | Example |
|---|---|---|
| Client-side | Client queries registry, picks instance | Netflix Eureka, Consul |
| Server-side | Load balancer queries registry | AWS ALB, Kubernetes Service |
| DNS-based | Use DNS SRV records | Kubernetes (default), Consul DNS |
| Environment | Inject service URLs at deploy time | Docker Compose, Helm values |

Kubernetes DNS-based (simplest):

```yaml
# payment-service resolves to:
# http://payment-service.payments-ns.svc.cluster.local:8080
# within the same namespace: http://payment-service:8080
```

## Observability in Microservices

Distributed tracing is non-negotiable:

```python
# Propagate trace context across services (OpenTelemetry)
from opentelemetry import trace
from opentelemetry.propagate import inject, extract

tracer = trace.get_tracer("order-service")

def place_order(order_data: dict, headers: dict):
    ctx = extract(headers)  # pull trace context from incoming request
    with tracer.start_as_current_span("place_order", context=ctx) as span:
        span.set_attribute("order.customer_id", order_data["customer_id"])
        outbound_headers = {}
        inject(outbound_headers)  # inject into outbound calls
        payment_client.charge(order_data, headers=outbound_headers)
```

> See also: `observability`

## Checklist

- [ ] Each service owns its own database — no shared tables or direct cross-DB queries
- [ ] Service boundaries align to domain bounded contexts, not technical layers
- [ ] All synchronous calls have explicit timeouts and retry with exponential backoff
- [ ] Circuit breaker configured for every downstream dependency
- [ ] Async event schemas are versioned; consumers tolerate unknown fields
- [ ] Saga compensating transactions defined for every distributed workflow
- [ ] API gateway handles auth, rate limiting, and trace injection centrally
- [ ] Distributed tracing propagated across all service calls (W3C traceparent)
- [ ] Dead-letter queues configured for all async consumers
- [ ] Health check endpoints (`/healthz`, `/readyz`) implemented in every service
- [ ] Services degrade gracefully when a dependency is unavailable (fallback/cache)
- [ ] Data contracts (API schemas, event schemas) reviewed before breaking changes
