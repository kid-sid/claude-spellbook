---
name: azure-service-bus
description: Azure Service Bus patterns for Python covering DefaultAzureCredential auth, queues vs topics/subscriptions, send/receive with peek-lock, dead-letter queues, sessions for ordered processing, subscription filters, scheduled messages, and retry configuration.
---

# Azure Service Bus

Production patterns for Azure Service Bus using the `azure-servicebus` Python SDK.

## When to Activate

- Writing code that imports `azure-servicebus` or `@azure/service-bus`
- Choosing between Service Bus queues, topics, and subscriptions
- Implementing reliable message processing with peek-lock and settlement
- Handling dead-lettered messages or poison message scenarios
- Ensuring ordered processing with Service Bus sessions
- Filtering messages per subscriber using SQL or correlation filters
- Scheduling messages for future delivery or implementing deferred processing
- Comparing Azure Service Bus against Azure Storage Queues or Event Hubs

## Authentication

```python
from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient

credential = DefaultAzureCredential()
client = ServiceBusClient(
    fully_qualified_namespace="myns.servicebus.windows.net",
    credential=credential,
)

# BAD: connection string embeds shared access key
client = ServiceBusClient.from_connection_string(
    "Endpoint=sb://myns.servicebus.windows.net/;SharedAccessKeyName=..."
)

# GOOD: keyless via RBAC role (Azure Service Bus Data Sender / Receiver)
client = ServiceBusClient(
    fully_qualified_namespace=os.environ["SERVICEBUS_NAMESPACE"],
    credential=DefaultAzureCredential(),
)
```

Always use `DefaultAzureCredential` and assign the minimum RBAC role:

| Role | Permission |
|---|---|
| `Azure Service Bus Data Sender` | Send messages only |
| `Azure Service Bus Data Receiver` | Receive and settle messages only |
| `Azure Service Bus Data Owner` | Full control — use only for admin tooling |

## Queues vs Topics/Subscriptions

| Factor | Queue | Topic + Subscriptions |
|---|---|---|
| Consumers | Single consumer group | Multiple independent consumers |
| Fan-out | No | Yes — each subscription gets a copy |
| Filtering | No | Yes — SQL or correlation filter per subscription |
| Ordering | Sessions only | Sessions only |
| Use case | Task queue, work distribution | Event fan-out, pub/sub |

```
Queue:      Producer → [Queue] → Consumer A
Topic:      Producer → [Topic] → [Sub: orders-billing]    → Billing Service
                               → [Sub: orders-shipping]   → Shipping Service
                               → [Sub: orders-analytics]  → Analytics Service
```

## Sending Messages

### Single Message

```python
from azure.servicebus import ServiceBusMessage
import json

def send_message(namespace: str, queue_name: str, body: dict, **props) -> None:
    credential = DefaultAzureCredential()
    with ServiceBusClient(namespace, credential) as client:
        with client.get_queue_sender(queue_name) as sender:
            message = ServiceBusMessage(
                json.dumps(body),
                subject=props.get("subject"),
                correlation_id=props.get("correlation_id"),
                message_id=props.get("message_id"),        # deduplication key
                time_to_live=props.get("ttl"),             # timedelta
                application_properties=props.get("properties", {}),
            )
            sender.send_messages(message)
```

### Batch Send

```python
def send_batch(namespace: str, queue_name: str, messages: list[dict]) -> None:
    with ServiceBusClient(namespace, DefaultAzureCredential()) as client:
        with client.get_queue_sender(queue_name) as sender:
            batch = sender.create_message_batch()
            for body in messages:
                try:
                    batch.add_message(ServiceBusMessage(json.dumps(body)))
                except ValueError:
                    # Batch full — send current batch and start a new one
                    sender.send_messages(batch)
                    batch = sender.create_message_batch()
                    batch.add_message(ServiceBusMessage(json.dumps(body)))
            if len(batch):
                sender.send_messages(batch)
```

### Scheduled Messages

```python
from datetime import datetime, timedelta, timezone

def schedule_message(namespace: str, queue_name: str, body: dict, delay: timedelta) -> int:
    enqueue_at = datetime.now(timezone.utc) + delay
    with ServiceBusClient(namespace, DefaultAzureCredential()) as client:
        with client.get_queue_sender(queue_name) as sender:
            seq_numbers = sender.schedule_messages(
                ServiceBusMessage(json.dumps(body)),
                enqueue_at,
            )
            return seq_numbers[0]  # use to cancel with cancel_scheduled_messages()
```

### Sending to a Topic

```python
def publish_event(namespace: str, topic_name: str, event_type: str, payload: dict) -> None:
    with ServiceBusClient(namespace, DefaultAzureCredential()) as client:
        with client.get_topic_sender(topic_name) as sender:
            sender.send_messages(ServiceBusMessage(
                json.dumps(payload),
                subject=event_type,
                application_properties={"event_type": event_type},
            ))
```

## Receiving Messages

### Peek-Lock (Recommended)

Locks the message for processing; must be explicitly settled. Ensures at-least-once delivery.

```python
from azure.servicebus import ServiceBusReceiveMode

def process_queue(namespace: str, queue_name: str, handler, max_messages: int = 10) -> None:
    with ServiceBusClient(namespace, DefaultAzureCredential()) as client:
        with client.get_queue_receiver(
            queue_name,
            receive_mode=ServiceBusReceiveMode.PEEK_LOCK,
            max_wait_time=5,
        ) as receiver:
            for msg in receiver.receive_messages(max_message_count=max_messages):
                try:
                    body = json.loads(str(msg))
                    handler(body)
                    receiver.complete_message(msg)      # ack — removes from queue
                except Exception as e:
                    if msg.delivery_count >= 3:
                        receiver.dead_letter_message(   # send to DLQ
                            msg,
                            reason="MaxRetriesExceeded",
                            error_description=str(e),
                        )
                    else:
                        receiver.abandon_message(msg)   # nack — requeues with backoff
```

### Settlement Methods

| Method | Effect | When to use |
|---|---|---|
| `complete_message` | Removes from queue | Processing succeeded |
| `abandon_message` | Returns to queue; increments `delivery_count` | Transient failure, will retry |
| `dead_letter_message` | Moves to DLQ with reason | Poison message, max retries exceeded |
| `defer_message` | Parks with sequence number for later retrieval | Out-of-order messages needing dependencies |

### Continuous Consumer (Long-Running)

```python
import threading

def start_consumer(namespace: str, queue_name: str, handler, stop_event: threading.Event) -> None:
    with ServiceBusClient(namespace, DefaultAzureCredential()) as client:
        with client.get_queue_receiver(queue_name, max_wait_time=5) as receiver:
            while not stop_event.is_set():
                messages = receiver.receive_messages(max_message_count=10, max_wait_time=5)
                if not messages:
                    continue
                for msg in messages:
                    try:
                        handler(json.loads(str(msg)))
                        receiver.complete_message(msg)
                    except Exception as e:
                        logger.exception("message_processing_failed", extra={"delivery_count": msg.delivery_count})
                        receiver.abandon_message(msg)
```

## Dead-Letter Queue

```python
def process_dlq(namespace: str, queue_name: str) -> list[dict]:
    dlq_path = f"{queue_name}/$deadletterqueue"
    dead_letters = []

    with ServiceBusClient(namespace, DefaultAzureCredential()) as client:
        with client.get_queue_receiver(
            dlq_path,
            receive_mode=ServiceBusReceiveMode.PEEK_LOCK,
        ) as receiver:
            for msg in receiver.receive_messages(max_message_count=50):
                dead_letters.append({
                    "body": json.loads(str(msg)),
                    "reason": msg.dead_letter_reason,
                    "description": msg.dead_letter_error_description,
                    "delivery_count": msg.delivery_count,
                    "enqueued_at": msg.enqueued_time_utc,
                })
                receiver.complete_message(msg)  # drain DLQ after inspection

    return dead_letters
```

Alert when DLQ message count (`ActiveMessageCount` on the DLQ entity) exceeds zero.

## Sessions (Ordered Processing)

Sessions guarantee FIFO ordering for messages with the same `session_id`. The queue/topic subscription must have `requires_session=True`.

```python
# Send with session ID (all messages for the same order stay ordered)
def send_with_session(namespace: str, queue_name: str, session_id: str, body: dict) -> None:
    with ServiceBusClient(namespace, DefaultAzureCredential()) as client:
        with client.get_queue_sender(queue_name) as sender:
            sender.send_messages(ServiceBusMessage(
                json.dumps(body),
                session_id=session_id,
            ))

# Receive a specific session
def process_session(namespace: str, queue_name: str, session_id: str, handler) -> None:
    with ServiceBusClient(namespace, DefaultAzureCredential()) as client:
        with client.get_queue_receiver(
            queue_name,
            session_id=session_id,
        ) as receiver:
            for msg in receiver.receive_messages(max_message_count=100):
                handler(json.loads(str(msg)))
                receiver.complete_message(msg)

# Accept the next available session (let Service Bus assign)
def process_next_session(namespace: str, queue_name: str, handler) -> None:
    with ServiceBusClient(namespace, DefaultAzureCredential()) as client:
        with client.get_queue_receiver(
            queue_name,
            session_id=NEXT_AVAILABLE_SESSION,  # from azure.servicebus
        ) as receiver:
            for msg in receiver.receive_messages(max_message_count=100, max_wait_time=10):
                handler(json.loads(str(msg)))
                receiver.complete_message(msg)
```

## Subscription Filters

```python
from azure.servicebus.management import ServiceBusAdministrationClient, SqlRuleFilter, CorrelationRuleFilter

admin = ServiceBusAdministrationClient(
    fully_qualified_namespace="myns.servicebus.windows.net",
    credential=DefaultAzureCredential(),
)

# SQL filter — route by message property
admin.create_rule(
    topic_name="orders",
    subscription_name="orders-eu",
    rule_name="eu-only",
    filter=SqlRuleFilter("Region = 'EU'"),
)

# Correlation filter — cheaper, matches on built-in or application properties
admin.create_rule(
    topic_name="orders",
    subscription_name="orders-priority",
    rule_name="priority-orders",
    filter=CorrelationRuleFilter(
        subject="order.placed",
        application_properties={"priority": "high"},
    ),
)

# Remove the default catch-all rule when adding selective filters
admin.delete_rule("orders", "orders-eu", "$Default")
```

| Filter type | Performance | Flexibility | Use when |
|---|---|---|---|
| `TrueRuleFilter` | Fast | None | Subscription receives everything (default) |
| `CorrelationRuleFilter` | Fastest | Subject, correlation ID, app properties | Property-based routing |
| `SqlRuleFilter` | Slower | Full SQL expression | Complex conditions across multiple properties |
| `FalseRuleFilter` | Fast | None | Disable subscription without deleting it |

## Retry Configuration

```python
from azure.servicebus import ServiceBusClient
from azure.core.pipeline.policies import RetryPolicy

# SDK-level retry (network/transient errors)
client = ServiceBusClient(
    fully_qualified_namespace="myns.servicebus.windows.net",
    credential=DefaultAzureCredential(),
    retry_total=5,
    retry_backoff_factor=1.5,
    retry_backoff_max=30,
)

# Message-level retry: set max_delivery_count on the queue/subscription
# (default 10 — messages exceeding this are auto-dead-lettered by Service Bus)
admin.update_queue(
    admin.get_queue("my-queue"),
    max_delivery_count=5,
    lock_duration=timedelta(minutes=2),   # must process within this window
)
```

## Error Handling

```python
from azure.servicebus.exceptions import (
    ServiceBusError,
    ServiceBusConnectionError,
    ServiceBusAuthorizationError,
    MessageLockLostError,
    SessionLockLostError,
    MessageAlreadySettled,
)

def safe_receive(receiver, handler, msg) -> None:
    try:
        handler(json.loads(str(msg)))
        receiver.complete_message(msg)
    except MessageLockLostError:
        # Lock expired before we could settle — message will reappear
        logger.warning("lock_expired", message_id=msg.message_id)
    except MessageAlreadySettled:
        # Duplicate settle call — safe to ignore
        pass
    except ServiceBusAuthorizationError:
        # RBAC role missing — fail fast, don't retry
        raise
    except ServiceBusConnectionError as e:
        logger.error("connection_lost", error=str(e))
        raise  # outer loop should reconnect
    except Exception as e:
        logger.exception("handler_failed")
        try:
            receiver.abandon_message(msg)
        except MessageAlreadySettled:
            pass
```

## Cost Controls

| Lever | Impact | How |
|---|---|---|
| Tier (Basic vs Standard vs Premium) | High | Basic: queues only, no topics/sessions; Standard: topics + sessions; Premium: dedicated capacity, no throttling |
| Message size | Medium | Standard max 256 KB; Premium max 100 MB — compress large payloads before sending |
| Message TTL | Medium | Set queue/message TTL to avoid accumulating unprocessed messages that waste storage |
| Auto-delete on idle | Low | Set `auto_delete_on_idle` on dev/staging queues to clean up abandoned resources |
| Duplicate detection window | Low | Enable on idempotent queues; deduplicated messages don't count toward throughput billing |

> See also: `event-driven`, `azure`, `observability`

## Checklist

- [ ] All clients use `DefaultAzureCredential` — no connection strings or SAS keys in code
- [ ] Minimum RBAC role assigned: `Data Sender` for producers, `Data Receiver` for consumers
- [ ] Receive mode is `PEEK_LOCK` for all reliable processing — not `RECEIVE_AND_DELETE`
- [ ] All messages explicitly settled: `complete`, `abandon`, or `dead_letter` — no silent drops
- [ ] `delivery_count` checked before settling; poison messages sent to DLQ with reason and description
- [ ] DLQ monitored — alert fires when `ActiveMessageCount` on `/$deadletterqueue` exceeds 0
- [ ] `max_delivery_count` set on queues/subscriptions (not left at default 10 without review)
- [ ] `lock_duration` set long enough to cover worst-case processing time
- [ ] Sessions used for entities requiring ordered or correlated processing
- [ ] Subscription `$Default` rule deleted when selective `CorrelationRuleFilter` or `SqlRuleFilter` is added
- [ ] SDK client reused across calls — not instantiated per message
- [ ] Message TTL set to prevent unbounded queue depth on abandoned consumers
