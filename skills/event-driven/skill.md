---
name: event-driven
description: Event-driven architecture patterns covering Kafka producer/consumer design, topic partitioning, consumer groups, event schema versioning, outbox pattern, dead-letter queues, idempotency, and event sourcing for Python, TypeScript, and Go.
---

# Event-Driven Architecture Patterns

Design and implementation patterns for reliable, scalable asynchronous systems using message brokers.

## When to Activate

- Decoupling services that currently call each other synchronously
- Designing Kafka topics, partitions, or consumer group topology
- Implementing event schemas with versioning and backward compatibility
- Ensuring exactly-once or at-least-once delivery semantics
- Setting up dead-letter queues and poison message handling
- Implementing the outbox pattern to avoid dual-write problems
- Building event sourcing or CQRS read-model projections

## Core Concepts

### Broker Comparison

| Broker | Retention | Ordering | Throughput | Best For |
|---|---|---|---|---|
| Kafka | Days–forever (log) | Per partition | Very high | Event streaming, audit log, replay |
| RabbitMQ | Until consumed | Per queue | High | Task queues, RPC, routing flexibility |
| AWS SQS | Up to 14 days | None (FIFO available) | High | Simple queues, AWS-native workloads |
| Redis Streams | Configurable | Per stream | High | Low-latency, simple consumers |
| GCP Pub/Sub | 7 days default | None | Very high | GCP-native, push subscriptions |

### Delivery Semantics

| Semantic | How | Tradeoff |
|---|---|---|
| At-least-once | Commit offset only after processing | Duplicates possible; consumer must be idempotent |
| At-most-once | Commit before processing | No duplicates; messages can be lost |
| Exactly-once | Transactional producer + idempotent consumer | Highest complexity; use outbox pattern instead |

Default to **at-least-once with idempotent consumers** — it's simpler than exactly-once and eliminates loss.

## Event Schema Design

### Event Envelope

```json
{
  "event_id": "01HXK4...",
  "event_type": "order.placed",
  "schema_version": "1.0",
  "occurred_at": "2025-06-01T12:00:00Z",
  "aggregate_id": "order-abc-123",
  "aggregate_type": "Order",
  "correlation_id": "req-xyz-456",
  "payload": {
    "customer_id": "cust-789",
    "total": "59.99",
    "currency": "USD",
    "items": [{ "sku": "WIDGET-01", "qty": 2, "unit_price": "29.99" }]
  }
}
```

Rules:
- `event_id`: globally unique (ULID or UUID v7) — used for idempotency keys
- `occurred_at`: when the fact happened, not when published
- `correlation_id`: propagate from the originating request for distributed tracing
- Monetary values: string decimal, not float

### Schema Versioning (Avro / JSON Schema)

```python
# GOOD: backward-compatible change — add optional field with default
{
  "event_type": "order.placed",
  "schema_version": "1.1",   # minor bump — consumers on 1.0 still work
  "payload": {
    "customer_id": "...",
    "total": "...",
    "promo_code": null        # new optional field, defaults to null
  }
}

# BAD: breaking changes
# - removing a field consumers depend on
# - renaming a field
# - changing a field type (string → int)
# → always create a new event type or bump major version
```

## Kafka Patterns

### Topic and Partition Design

```
# Naming: <domain>.<entity>.<event-type> or <domain>.<entity>
orders.placed
orders.cancelled
payments
inventory.stock-updates

# Partition key selection — determines ordering guarantee
producer.produce(topic="orders", key=order.customer_id, ...)  # all orders per customer are ordered
producer.produce(topic="payments", key=payment.order_id, ...)  # all events per order are ordered

# Partition count tradeoffs
low partitions (1–6):   easy rebalancing, less parallelism
high partitions (12+):  more parallelism, more consumer instances, slower rebalance
rule: start with max(consumer_instances * 2, 12), increase later
```

### Python Producer

```python
from confluent_kafka import Producer, KafkaException
import json, uuid
from datetime import datetime, timezone

producer = Producer({
    "bootstrap.servers": "kafka:9092",
    "acks": "all",                    # wait for all ISR replicas
    "retries": 5,
    "retry.backoff.ms": 500,
    "enable.idempotence": True,       # exactly-once producer semantics
    "compression.type": "lz4",
})

def publish_event(topic: str, key: str, event_type: str, payload: dict):
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "schema_version": "1.0",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    producer.produce(
        topic=topic,
        key=key.encode(),
        value=json.dumps(event).encode(),
        on_delivery=_delivery_report,
    )
    producer.poll(0)  # trigger callbacks without blocking

def _delivery_report(err, msg):
    if err:
        logger.error("delivery_failed", topic=msg.topic(), error=str(err))

producer.flush()  # call at shutdown
```

### Python Consumer

```python
from confluent_kafka import Consumer, KafkaError
import json

consumer = Consumer({
    "bootstrap.servers": "kafka:9092",
    "group.id": "notification-service",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,      # manual commit after processing
    "max.poll.interval.ms": 300_000,
})

consumer.subscribe(["orders"])

try:
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError.PARTITION_EOF:
                continue
            raise KafkaException(msg.error())

        event = json.loads(msg.value())
        try:
            handle_event(event)
            consumer.commit(message=msg)   # commit only after success
        except Exception as e:
            logger.error("processing_failed", event_id=event["event_id"], error=str(e))
            # don't commit — message will be redelivered
finally:
    consumer.close()
```

### TypeScript Consumer (KafkaJS)

```typescript
import { Kafka } from "kafkajs";

const kafka = new Kafka({ brokers: ["kafka:9092"] });
const consumer = kafka.consumer({ groupId: "notification-service" });

await consumer.connect();
await consumer.subscribe({ topics: ["orders"], fromBeginning: false });

await consumer.run({
  autoCommit: false,
  eachMessage: async ({ topic, partition, message, heartbeat }) => {
    const event = JSON.parse(message.value!.toString());
    try {
      await handleEvent(event);
      await consumer.commitOffsets([{
        topic, partition,
        offset: (Number(message.offset) + 1).toString(),
      }]);
    } catch (err) {
      logger.error({ eventId: event.event_id, err }, "processing_failed");
      throw err;  // re-throw to pause and retry
    }
  },
});
```

### Go Consumer (Sarama)

```go
import "github.com/IBM/sarama"

type OrderHandler struct{ db *sql.DB }

func (h *OrderHandler) Setup(_ sarama.ConsumerGroupSession) error   { return nil }
func (h *OrderHandler) Cleanup(_ sarama.ConsumerGroupSession) error { return nil }

func (h *OrderHandler) ConsumeClaim(sess sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
    for msg := range claim.Messages() {
        var event Event
        if err := json.Unmarshal(msg.Value, &event); err != nil {
            logger.Error("unmarshal_failed", "offset", msg.Offset)
            sess.MarkMessage(msg, "")  // skip unparseable messages
            continue
        }
        if err := h.handle(sess.Context(), event); err != nil {
            return err  // stop processing; session will restart
        }
        sess.MarkMessage(msg, "")
    }
    return nil
}
```

## Idempotency

Consumers must handle duplicate messages — at-least-once delivery guarantees redelivery on failure.

```python
# Pattern: idempotency key in a processed-events table
def handle_order_placed(event: dict, db: Session):
    event_id = event["event_id"]

    # Check if already processed
    if db.query(ProcessedEvent).filter_by(event_id=event_id).first():
        logger.info("duplicate_skipped", event_id=event_id)
        return

    # Process in a transaction that also inserts the idempotency record
    with db.begin():
        create_notification(event["payload"])
        db.add(ProcessedEvent(event_id=event_id, processed_at=datetime.utcnow()))
```

```typescript
// Alternative: upsert on natural key (e.g. order_id)
await db.transaction(async (trx) => {
  await trx("notifications")
    .insert({ order_id: event.payload.order_id, customer_id: event.payload.customer_id })
    .onConflict("order_id")
    .ignore();  // safe to call multiple times
});
```

## Outbox Pattern

Solves dual-write: never publish directly from application code after a DB write — they can desync.

```
# BAD: dual write (either step can fail independently)
BEGIN TRANSACTION
  INSERT INTO orders (...)
COMMIT
kafka.produce("order.placed", ...)   # ← this can fail silently

# GOOD: outbox pattern
BEGIN TRANSACTION
  INSERT INTO orders (...)
  INSERT INTO outbox (event_type, payload, published=false, ...)  # same transaction
COMMIT

# Separate relay process (Debezium CDC or polling relay)
SELECT * FROM outbox WHERE published = false ORDER BY created_at LIMIT 100
→ produce to Kafka
→ UPDATE outbox SET published = true WHERE id IN (...)
```

```python
# Polling relay (simple, no CDC dependency)
def relay_outbox(db: Session, producer: Producer):
    events = db.query(OutboxEvent).filter_by(published=False).limit(100).all()
    for event in events:
        producer.produce(
            topic=event.topic,
            key=event.aggregate_id.encode(),
            value=event.payload.encode(),
        )
    producer.flush()
    for event in events:
        event.published = True
    db.commit()
```

## Dead-Letter Queues

```python
# Python — send to DLQ after max retries
MAX_RETRIES = 3

def handle_with_dlq(consumer, dlq_producer, msg):
    retry_count = int(msg.headers().get("retry-count", b"0"))
    event = json.loads(msg.value())

    try:
        process_event(event)
        consumer.commit(message=msg)
    except Exception as e:
        if retry_count >= MAX_RETRIES:
            dlq_producer.produce(
                topic=f"{msg.topic()}.dlq",
                key=msg.key(),
                value=msg.value(),
                headers={"original-topic": msg.topic(), "error": str(e)},
            )
            consumer.commit(message=msg)  # move past it
            logger.error("sent_to_dlq", event_id=event["event_id"])
        else:
            # Re-queue with incremented retry count (or let Kafka retry via pause)
            logger.warning("retry", attempt=retry_count + 1, event_id=event["event_id"])
```

DLQ naming convention: `<original-topic>.dlq`
DLQ review: alert on DLQ lag > 0; investigate and replay or discard manually.

## Event Sourcing

Store state as an append-only log of events; derive current state by replaying.

```python
# Events are facts, not commands
EVENTS = [
    {"type": "OrderCreated",   "payload": {"customer_id": "c1", "items": [...]}},
    {"type": "ItemAdded",      "payload": {"sku": "X", "qty": 1}},
    {"type": "OrderConfirmed", "payload": {"confirmed_at": "2025-01-01T..."}},
]

def replay(events: list[dict]) -> Order:
    order = Order()
    for event in events:
        match event["type"]:
            case "OrderCreated":   order.apply_created(event["payload"])
            case "ItemAdded":      order.apply_item_added(event["payload"])
            case "OrderConfirmed": order.apply_confirmed(event["payload"])
    return order

# Snapshot: periodically persist current state to avoid full replay
# Projection: consume event stream to build read models (CQRS read side)
```

| Use Event Sourcing When | Avoid When |
|---|---|
| Audit trail is a first-class requirement | Simple CRUD with no history needs |
| Need to replay history for new features | Team unfamiliar with the pattern |
| Multiple read models from one write model | Strong consistency required across aggregates |
| Temporal queries ("state at time T") | Simple, low-volume domain |

> See also: `microservices`, `observability`

## Checklist

- [ ] Event envelope includes `event_id`, `event_type`, `schema_version`, `occurred_at`, `correlation_id`
- [ ] Partition key chosen to guarantee ordering for events that must be ordered
- [ ] Producer uses `acks=all` and `enable.idempotence=true`
- [ ] Consumer commits offsets manually after successful processing
- [ ] All consumers are idempotent (duplicate `event_id` handled gracefully)
- [ ] Outbox pattern used — never dual-write to DB and broker in separate transactions
- [ ] Dead-letter queue configured; alerts fire when DLQ lag exceeds threshold
- [ ] Event schema changes are backward-compatible (add optional fields only)
- [ ] Consumer group IDs are service-specific and stable across deploys
- [ ] Dead-letter messages include original topic, offset, and error reason in headers
- [ ] Retention period set to cover the longest plausible consumer downtime plus buffer
