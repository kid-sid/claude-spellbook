---
name: webhooks
description: Use when designing a webhook delivery system, implementing HMAC signature verification on a receiver, handling retries and failures on the sender side, building idempotent webhook consumers, or testing webhook integrations locally.
---

# Webhooks

Patterns for reliable webhook delivery, signature verification, idempotent consumption, and local testing.

## When to Activate

- Designing a system that pushes events to external URLs
- Implementing HMAC signature verification on a webhook receiver
- Building retry and failure handling on the webhook sender side
- Making a webhook consumer idempotent (safe to receive twice)
- Exposing and documenting a webhook API for third-party integrations
- Testing webhook integrations locally without a public URL
- Auditing an existing webhook implementation for security or reliability gaps

---

## Sender vs. Receiver Responsibilities

| Concern | Sender (you push) | Receiver (you consume) |
|---|---|---|
| Signing | Sign every payload with HMAC | Verify signature before processing |
| Delivery | Retry with backoff on non-2xx | Return 2xx immediately, process async |
| Ordering | Add sequence or timestamp | Don't assume ordered delivery |
| Idempotency | Include a stable event ID | Deduplicate on event ID |
| Schema | Version the event type | Handle unknown fields gracefully |

---

## Event Envelope Design

Every webhook payload should include a consistent envelope regardless of event type.

```json
{
  "id": "evt_01HX4K9MZQR8FVNJ2Y3BCD5",
  "type": "order.completed",
  "version": "2024-01",
  "created_at": "2024-01-15T10:30:00Z",
  "data": {
    "order_id": "ord_789",
    "amount": 4999,
    "currency": "usd"
  }
}
```

| Field | Purpose |
|---|---|
| `id` | Stable, unique event ID — used for deduplication |
| `type` | Namespaced event name (`resource.action`) |
| `version` | Schema version — allows evolving payloads without breaking receivers |
| `created_at` | When the event occurred (not when it was delivered) |
| `data` | Event-specific payload |

---

## HMAC Signature Verification

Never trust a webhook payload without verifying its signature. Use a **constant-time comparison** to prevent timing attacks.

### Signing (Sender)

```python
# Python
import hmac, hashlib, json, time

def sign_payload(payload: dict, secret: str) -> tuple[str, str]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signed = f"{timestamp}.{body.decode()}"
    sig = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}", body
```

```typescript
// TypeScript
import { createHmac } from "crypto";

function signPayload(payload: object, secret: string): { signature: string; body: string } {
  const body = JSON.stringify(payload);
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const signed = `${timestamp}.${body}`;
  const sig = createHmac("sha256", secret).update(signed).digest("hex");
  return { signature: `t=${timestamp},v1=${sig}`, body };
}
```

```go
// Go
func SignPayload(payload []byte, secret string, now time.Time) string {
    timestamp := strconv.FormatInt(now.Unix(), 10)
    signed := timestamp + "." + string(payload)
    mac := hmac.New(sha256.New, []byte(secret))
    mac.Write([]byte(signed))
    sig := hex.EncodeToString(mac.Sum(nil))
    return fmt.Sprintf("t=%s,v1=%s", timestamp, sig)
}
```

### Verifying (Receiver)

```python
# Python — FastAPI
import hmac, hashlib, time
from fastapi import Request, HTTPException

TOLERANCE_SECONDS = 300  # reject replays older than 5 minutes

async def verify_webhook(request: Request, secret: str) -> bytes:
    sig_header = request.headers.get("X-Webhook-Signature", "")
    body = await request.body()

    parts = dict(p.split("=", 1) for p in sig_header.split(","))
    timestamp = parts.get("t", "")
    received_sig = parts.get("v1", "")

    # Reject replayed requests
    if abs(time.time() - int(timestamp)) > TOLERANCE_SECONDS:
        raise HTTPException(400, "Webhook timestamp too old")

    expected = hmac.new(
        secret.encode(),
        f"{timestamp}.{body.decode()}".encode(),
        hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison — prevents timing attacks
    if not hmac.compare_digest(expected, received_sig):
        raise HTTPException(400, "Invalid webhook signature")

    return body
```

```typescript
// TypeScript — Express
import { createHmac, timingSafeEqual } from "crypto";
import { Request, Response, NextFunction } from "express";

const TOLERANCE_SECONDS = 300;

export function verifyWebhook(secret: string) {
  return (req: Request, res: Response, next: NextFunction) => {
    const header = req.headers["x-webhook-signature"] as string ?? "";
    const parts = Object.fromEntries(header.split(",").map((p) => p.split("=")));
    const { t: timestamp, v1: receivedSig } = parts;

    if (Math.abs(Date.now() / 1000 - Number(timestamp)) > TOLERANCE_SECONDS) {
      return res.status(400).json({ error: "Webhook timestamp too old" });
    }

    const body = (req as any).rawBody as Buffer; // requires rawBody middleware
    const expected = createHmac("sha256", secret)
      .update(`${timestamp}.${body}`)
      .digest("hex");

    if (!timingSafeEqual(Buffer.from(expected), Buffer.from(receivedSig))) {
      return res.status(400).json({ error: "Invalid webhook signature" });
    }

    next();
  };
}
```

```go
// Go
func VerifyWebhook(r *http.Request, body []byte, secret string) error {
    header := r.Header.Get("X-Webhook-Signature")
    parts := parseHeader(header) // split "t=...,v1=..." into map
    timestamp, received := parts["t"], parts["v1"]

    ts, _ := strconv.ParseInt(timestamp, 10, 64)
    if math.Abs(float64(time.Now().Unix()-ts)) > 300 {
        return errors.New("webhook timestamp too old")
    }

    mac := hmac.New(sha256.New, []byte(secret))
    mac.Write([]byte(timestamp + "." + string(body)))
    expected := hex.EncodeToString(mac.Sum(nil))

    if !hmac.Equal([]byte(expected), []byte(received)) {
        return errors.New("invalid webhook signature")
    }
    return nil
}
```

---

## Reliable Delivery (Sender)

### Delivery Pipeline

```
Event occurs → persist to outbox → worker picks up → HTTP POST → record result
                                                              ↓
                                                    success: mark delivered
                                                    failure: schedule retry
```

Use the **transactional outbox pattern** — write the event to a DB table in the same transaction as the business change. A background worker reads and delivers it. This prevents events being lost if the app crashes between the DB write and the HTTP call.

```python
# Python — outbox record
@dataclass
class WebhookDelivery:
    id: str
    endpoint_url: str
    payload: dict
    attempt: int = 0
    max_attempts: int = 5
    next_attempt_at: datetime = field(default_factory=datetime.utcnow)
    delivered_at: datetime | None = None
    last_error: str | None = None
```

### Retry Schedule

| Attempt | Delay |
|---|---|
| 1st retry | 30 seconds |
| 2nd retry | 5 minutes |
| 3rd retry | 30 minutes |
| 4th retry | 2 hours |
| 5th retry | 8 hours |
| After max | Move to dead-letter queue |

```python
def next_retry_delay(attempt: int) -> int:
    schedule = [30, 300, 1800, 7200, 28800]
    return schedule[min(attempt, len(schedule) - 1)]
```

### Delivery Worker

```python
import httpx

async def deliver_webhook(delivery: WebhookDelivery, secret: str) -> None:
    sig, body = sign_payload(delivery.payload, secret)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                delivery.endpoint_url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": sig,
                    "X-Webhook-ID": delivery.id,
                },
            )
        if r.status_code < 200 or r.status_code >= 300:
            raise ValueError(f"non-2xx: {r.status_code}")
        await mark_delivered(delivery.id)
    except Exception as exc:
        await schedule_retry(delivery, error=str(exc))
```

---

## Idempotent Consumers

Webhooks can be delivered more than once. Always deduplicate on `event.id`.

```python
# Python — Redis deduplication
import redis.asyncio as redis

async def handle_webhook(event: dict, r: redis.Redis) -> None:
    event_id = event["id"]
    key = f"webhook:seen:{event_id}"

    # SET NX — only set if not already present
    already_seen = not await r.set(key, "1", nx=True, ex=86400)
    if already_seen:
        return  # duplicate — safe to ignore

    # Process after deduplication
    await process_event(event)
```

```typescript
// TypeScript — DB-based deduplication
async function handleWebhook(event: WebhookEvent): Promise<void> {
  const inserted = await db.webhookEvent.upsert({
    where: { id: event.id },
    create: { id: event.id, type: event.type, processedAt: null },
    update: {}, // no-op if already exists
  });

  if (inserted.processedAt) return; // already processed

  await processEvent(event);
  await db.webhookEvent.update({ where: { id: event.id }, data: { processedAt: new Date() } });
}
```

---

## Receiver Response Contract

| Scenario | Response | Notes |
|---|---|---|
| Accepted for processing | `200 OK` | Body ignored by sender |
| Duplicate (already processed) | `200 OK` | Not an error — idempotent |
| Invalid signature | `400 Bad Request` | Do not retry |
| Unknown event type | `200 OK` | Accept and ignore unknown types |
| Downstream not ready | `503 Service Unavailable` | Sender will retry |

**Always return 2xx immediately.** Do the actual work asynchronously (queue it). A slow receiver causes the sender to timeout and retry unnecessarily.

```python
# FastAPI — accept immediately, process async
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await verify_webhook(request, secret=STRIPE_SECRET)
    event = json.loads(body)
    background_tasks.add_task(process_stripe_event, event)
    return {"received": True}  # 200 immediately
```

---

## Local Testing

```bash
# Use a tunnel to expose localhost
npx localtunnel --port 3000 --subdomain my-app
# or
ngrok http 3000

# Replay a real webhook for testing
curl -X POST http://localhost:3000/webhooks \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: t=1234567890,v1=abc..." \
  -d '{"id":"evt_test","type":"order.completed","data":{}}'

# Stripe CLI — replay events against local server
stripe listen --forward-to localhost:3000/webhooks/stripe
stripe trigger payment_intent.succeeded
```

---

## Red Flags

- **No signature verification** — any caller can send a fake payload; always verify HMAC before touching the body.
- **String equality for signature comparison** — use `hmac.compare_digest` / `timingSafeEqual` / `hmac.Equal`; plain `==` leaks timing information.
- **No timestamp validation** — without a replay window check, an attacker can resend a captured payload indefinitely.
- **Synchronous processing in the handler** — a slow downstream makes the receiver timeout; the sender retries, creating a storm; always return 2xx immediately and queue the work.
- **Not idempotent** — at-least-once delivery is the norm; without deduplication a retry charges a customer twice or sends a duplicate email.
- **Retrying 4xx responses** — a 400 or 401 will never succeed; only retry 5xx and network errors.
- **No dead-letter queue** — events that exhaust retries silently disappear; always persist to a DLQ for inspection and manual replay.
- **Delivering directly from the request handler** — if the app crashes mid-delivery, the event is lost; use a transactional outbox instead.

---

## Checklist

- [ ] Every outgoing payload signed with HMAC-SHA256 and includes a timestamp
- [ ] Receiver verifies signature with constant-time comparison before processing
- [ ] Replay window enforced — payloads older than 5 minutes rejected
- [ ] Receiver returns 2xx immediately — actual processing is async
- [ ] Consumer is idempotent — deduplicates on `event.id` via Redis or DB upsert
- [ ] Sender uses transactional outbox — event persisted before delivery attempt
- [ ] Retry schedule uses increasing delays — no fixed-interval hammering
- [ ] 4xx responses not retried — only 5xx and network errors trigger retry
- [ ] Dead-letter queue captures events that exhaust all retry attempts
- [ ] Webhook endpoint URL and signing secret stored in env vars — not hardcoded
- [ ] Unknown event types accepted with 200 and silently ignored
- [ ] Local testing flow documented — tunnel or CLI replay tool configured
