---
name: observability
description: "Observability stack: structured logging with correlation IDs (structlog/pino/slog), Prometheus metrics (counters, histograms, RED/USE methods), OpenTelemetry distributed tracing (spans, context propagation, sampling), alerting rule design, SLO/SLI/error budgets, and Grafana golden signals dashboards."
---

# Observability

Observability is the practice of instrumenting systems so you can understand their internal state from external outputs — logs, metrics, and traces.

## When to Activate

- Adding logging to a new service or endpoint
- Setting up Prometheus metrics for a service
- Implementing distributed tracing across services
- Writing alerting rules or on-call runbooks
- Defining SLOs and error budgets for a service
- Building a Grafana dashboard for a service
- Debugging a production issue using logs, metrics, or traces

---

## The Three Pillars

| Pillar | Question it answers | Best tool | When to reach for it |
|--------|---------------------|-----------|----------------------|
| Logs | "What happened?" | structlog, pino, slog | Debugging specific errors, audit trails |
| Metrics | "How is the system performing?" | Prometheus | Trending, alerting, capacity |
| Traces | "Why is this slow / where did it fail?" | OpenTelemetry | Latency debugging, distributed request flow |

OpenTelemetry is the unifying standard across all three pillars: one SDK for logs, metrics, and traces, vendor-agnostic, with exporters to any backend (Grafana, Datadog, Honeycomb, Jaeger, etc.).

---

## Structured Logging

Always emit logs as JSON. Human-readable plaintext is fine in development, but production logs must be machine-parseable. Never log sensitive data (PII, card numbers, passwords, tokens).

### Mandatory Fields

Every log line must include:

| Field | Type | Example |
|-------|------|---------|
| `timestamp` | ISO 8601 | `2024-01-15T10:30:00.000Z` |
| `level` | string | `INFO` |
| `service` | string | `payment-service` |
| `trace_id` | string | `abc123...` |
| `span_id` | string | `def456...` |
| `request_id` | string | UUID per HTTP request |
| `message` | string | Human-readable description |

### Log Levels

| Level | When to use | Example |
|-------|-------------|---------|
| DEBUG | Verbose dev-only detail | "Entering validatePayment()" |
| INFO | Normal operational events | "Payment processed for order 123" |
| WARN | Unexpected but recoverable | "Retry attempt 2/3 for order 123" |
| ERROR | Failure that needs attention | "Payment declined: card expired" |
| FATAL/CRITICAL | Service cannot continue | "DB connection pool exhausted" |

Rule: use INFO in production, DEBUG only in development. WARN does not page on-call. ERROR does.

### Code Examples

Python with `structlog`:

```python
import structlog

logger = structlog.get_logger()

# Configure once at startup
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

# Usage — bind context, then log
log = logger.bind(service="payment-service", request_id=request_id)
log.info("payment.processing", order_id=order_id, amount=amount)
log.error("payment.failed", order_id=order_id, error=str(e))
```

TypeScript with `pino`:

```typescript
import pino from 'pino';

const logger = pino({
  level: process.env.LOG_LEVEL ?? 'info',
  base: { service: 'payment-service' },
});

const requestLogger = logger.child({ requestId, traceId });
requestLogger.info({ orderId, amount }, 'payment.processing');
requestLogger.error({ orderId, err }, 'payment.failed');
```

Go with `slog` (stdlib, Go 1.21+):

```go
import "log/slog"

logger := slog.With(
    slog.String("service", "payment-service"),
    slog.String("request_id", requestID),
)

logger.Info("payment.processing",
    slog.String("order_id", orderID),
    slog.Float64("amount", amount),
)
logger.Error("payment.failed",
    slog.String("order_id", orderID),
    slog.String("error", err.Error()),
)
```

### Correlation ID Propagation

Correlation IDs let you follow a single request across multiple services and log entries.

- Generate `request_id` at the edge (API gateway or the first handler to receive the request)
- Pass it downstream via HTTP headers: `X-Request-ID` or `X-Correlation-ID`
- Include the ID in all log lines for the duration of that request
- Include the ID in error responses so users can report it to support
- In async flows (message queues, event streams): embed `correlation_id` in the message payload itself, not just headers

Middleware pattern (Express/Node):

```typescript
import { v4 as uuidv4 } from 'uuid';

app.use((req, res, next) => {
  const requestId = req.headers['x-request-id'] as string ?? uuidv4();
  req.requestId = requestId;
  res.setHeader('X-Request-ID', requestId);
  req.log = logger.child({ requestId });
  next();
});
```

Middleware pattern (Python/FastAPI):

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class CorrelationIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        with structlog.contextvars.bound_contextvars(request_id=request_id):
            response = await call_next(request)
            response.headers["x-request-id"] = request_id
            return response
```

---

## Metrics with Prometheus

Prometheus is a pull-based metrics system: your service exposes a `/metrics` endpoint and Prometheus scrapes it on a configured interval (typically 15–30 seconds).

### Metric Types

| Type | Use for | Example |
|------|---------|---------|
| Counter | Things that only go up (requests, errors) | `http_requests_total` |
| Gauge | Values that go up and down | `active_connections`, `memory_bytes` |
| Histogram | Distribution of values (latency, size) | `request_duration_seconds` |
| Summary | Like histogram, but calculates quantiles client-side | Avoid — prefer Histogram |

Prefer Histogram over Summary. Histograms can be aggregated across instances in PromQL; Summaries cannot.

### Naming Conventions

Pattern: `<namespace>_<subsystem>_<name>_<unit>`

- `payment_service_http_requests_total` — counter; `_total` suffix implies count
- `payment_service_db_query_duration_seconds` — histogram; always include unit in the name
- `payment_service_cache_hit_ratio` — gauge; ratio 0–1, no unit suffix needed
- `payment_service_queue_depth` — gauge; current number of items in queue

Never include label values in metric names. Use labels instead:

```
# WRONG
http_500_errors_total

# RIGHT
http_errors_total{status="500"}
```

### Label Cardinality Trap

Labels multiply time series. A metric with two labels each having 10 values creates 100 series. High-cardinality labels (user IDs, order IDs, full URL paths with path parameters) can create millions of series, crashing Prometheus.

```python
# BAD — creates a new time series for every unique user ID
http_requests_total.labels(user_id=user.id).inc()

# GOOD — low cardinality labels only
http_requests_total.labels(method="POST", endpoint="/payments", status="200").inc()
```

Safe label values: HTTP method, endpoint (normalized, no IDs), status code, region, environment, service version.

### RED Method (for services)

Use RED to define the minimum set of metrics for any service:

- **R**ate: requests per second
  ```promql
  rate(http_requests_total[5m])
  ```
- **E**rrors: error rate as a fraction of total traffic
  ```promql
  rate(http_requests_total{status=~"5.."}[5m])
  / rate(http_requests_total[5m])
  ```
- **D**uration: latency at the 95th percentile
  ```promql
  histogram_quantile(0.95, rate(request_duration_seconds_bucket[5m]))
  ```

### USE Method (for resources)

Use USE to define metrics for infrastructure and resource-level components:

- **U**tilization: percentage of time the resource is busy (e.g., CPU%, disk I/O%)
- **S**aturation: work that is queued because it cannot be served immediately (e.g., run queue length)
- **E**rrors: error events from the resource (e.g., disk I/O errors, network drops)

### Code Examples

Python with `prometheus_client`:

```python
from prometheus_client import Counter, Histogram, start_http_server

REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)
REQUEST_DURATION = Histogram(
    'request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[.005, .01, .025, .05, .1, .25, .5, 1, 2.5]
)

# Usage
with REQUEST_DURATION.labels(method='POST', endpoint='/payments').time():
    result = process_payment()
REQUEST_COUNT.labels(method='POST', endpoint='/payments', status='200').inc()

# Expose metrics endpoint
start_http_server(8000)
```

TypeScript with `prom-client`:

```typescript
import { Counter, Histogram, collectDefaultMetrics, register } from 'prom-client';

collectDefaultMetrics({ prefix: 'payment_service_' });

const requestCount = new Counter({
  name: 'http_requests_total',
  help: 'Total HTTP requests',
  labelNames: ['method', 'endpoint', 'status'],
});

const requestDuration = new Histogram({
  name: 'request_duration_seconds',
  help: 'HTTP request duration',
  labelNames: ['method', 'endpoint'],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5],
});

// Expose metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});
```

Go with `prometheus/client_golang`:

```go
import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
    requestCount = promauto.NewCounterVec(prometheus.CounterOpts{
        Name: "http_requests_total",
        Help: "Total HTTP requests",
    }, []string{"method", "endpoint", "status"})

    requestDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
        Name:    "request_duration_seconds",
        Help:    "HTTP request duration",
        Buckets: prometheus.DefBuckets,
    }, []string{"method", "endpoint"})
)

// Expose metrics endpoint
http.Handle("/metrics", promhttp.Handler())
```

---

## Distributed Tracing with OpenTelemetry

### Concepts

- **Trace**: the complete end-to-end journey of a single request, identified by a unique `trace_id`
- **Span**: a single named unit of work within a trace (has a start time, end time, status, and attributes); spans form a tree
- **Context propagation**: the mechanism for passing `trace_id` and `span_id` across service boundaries via HTTP headers; use the W3C `traceparent` header (standardized, supported everywhere)
- **Collector**: a sidecar or standalone service (otel-collector) that receives span data, batches it, and forwards it to a backend (Jaeger, Tempo, etc.)

### Auto-Instrumentation vs Manual Spans

- **Auto-instrumentation**: instrument HTTP frameworks, DB drivers, gRPC clients automatically — get traces with zero code changes (install the SDK + one setup file)
- **Manual spans**: wrap custom business logic to make it visible in traces (e.g., "processing payment", "calling fraud check API", "serializing response")

When in doubt: start with auto-instrumentation to get baseline visibility, then add manual spans where you need business context.

### Setup (Python)

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Bootstrap once at startup
provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4317"))
)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("payment-service")

# Manual span around business logic
with tracer.start_as_current_span("process_payment") as span:
    span.set_attribute("order.id", order_id)
    span.set_attribute("payment.amount", amount)
    span.set_attribute("payment.currency", currency)
    result = charge_card(card_token, amount)
    span.set_attribute("payment.result", result.status)
```

### Setup (TypeScript)

```typescript
import { trace, SpanStatusCode, context } from '@opentelemetry/api';
import { NodeTracerProvider } from '@opentelemetry/sdk-trace-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';

// Bootstrap once at startup
const provider = new NodeTracerProvider();
provider.addSpanProcessor(
  new BatchSpanProcessor(
    new OTLPTraceExporter({ url: 'http://otel-collector:4317' })
  )
);
provider.register();

const tracer = trace.getTracer('payment-service');

// Manual span with error handling
async function processPayment(orderId: string, amount: number) {
  const span = tracer.startSpan('process_payment');
  return context.with(trace.setSpan(context.active(), span), async () => {
    span.setAttribute('order.id', orderId);
    span.setAttribute('payment.amount', amount);
    try {
      const result = await chargeCard(orderId, amount);
      span.setStatus({ code: SpanStatusCode.OK });
      return result;
    } catch (err) {
      span.recordException(err as Error);
      span.setStatus({ code: SpanStatusCode.ERROR, message: (err as Error).message });
      throw err;
    } finally {
      span.end();
    }
  });
}
```

### Setup (Go)

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func initTracer(ctx context.Context) (*trace.TracerProvider, error) {
    exporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint("otel-collector:4317"),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }
    tp := trace.NewTracerProvider(
        trace.WithBatcher(exporter),
        trace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName("payment-service"),
        )),
    )
    otel.SetTracerProvider(tp)
    return tp, nil
}

// Usage
tracer := otel.Tracer("payment-service")
ctx, span := tracer.Start(ctx, "process_payment")
defer span.End()
span.SetAttributes(
    attribute.String("order.id", orderID),
    attribute.Float64("payment.amount", amount),
)
```

### Sampling Strategies

| Strategy | Description | Best for |
|----------|-------------|----------|
| Head sampling (always on) | Sample 100% of traces | Development, test environments |
| Head sampling (probabilistic) | Sample X% of traces at trace start | Steady-state production traffic cost control |
| Head sampling (never) | Drop all traces | When tracing a noisy low-value service |
| Tail sampling | Sample based on outcome (errors, slow spans) | Catch 100% of errors while sampling fast successes |
| Parent-based | Follow the upstream caller's sampling decision | Microservices (honor the decision made at the edge) |

Recommended production setup: parent-based at 10% for happy path + tail sampling to capture 100% of errors and traces with p99+ latency.

---

## Alerting Design

### Symptom-Based vs Cause-Based

Alert on symptoms (what users experience), not causes (what resources are doing):

| Type | Example | Why |
|------|---------|-----|
| Symptom (preferred) | "5xx error rate > 1% for 5 minutes" | Users are directly affected right now |
| Cause (avoid as primary) | "CPU usage > 80%" | CPU can spike without user impact; often too noisy |
| Cause (use for capacity) | "Disk > 85% full" | Predictive; gives time to act before impact |

### Alert Design Rules

- Every alert must link to a runbook that explains diagnosis and remediation steps
- `severity: critical` means page someone immediately — it is happening now and users are affected
- `severity: warning` means investigate during business hours — degraded but not yet user-impacting
- Avoid alerting on individual metrics; alert on SLO burn rate where possible
- Every alert should be actionable: if you cannot do anything about it, do not alert on it
- Add a `for:` duration to avoid flapping on transient spikes (5 minutes is a safe default)

### Prometheus Alerting Rule Example

```yaml
groups:
  - name: payment-service
    rules:
      - alert: HighErrorRate
        expr: |
          rate(http_requests_total{service="payment-service",status=~"5.."}[5m])
          / rate(http_requests_total{service="payment-service"}[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
          service: payment-service
          team: payments
        annotations:
          summary: "High error rate on payment-service"
          description: "Error rate is {{ $value | humanizePercentage }} over last 5 minutes"
          runbook: "https://wiki.example.com/runbooks/payment-service#high-error-rate"

      - alert: HighLatencyP99
        expr: |
          histogram_quantile(0.99,
            rate(request_duration_seconds_bucket{service="payment-service"}[5m])
          ) > 2.0
        for: 5m
        labels:
          severity: warning
          service: payment-service
          team: payments
        annotations:
          summary: "P99 latency above 2s on payment-service"
          description: "P99 is {{ $value | humanizeDuration }}"
          runbook: "https://wiki.example.com/runbooks/payment-service#high-latency"
```

---

## SLOs and Error Budgets

### Hierarchy

- **SLI** (Service Level Indicator): the specific metric being measured (e.g., fraction of HTTP requests returning 2xx, p99 latency)
- **SLO** (Service Level Objective): the internal target for an SLI (e.g., 99.9% of requests return 2xx over a rolling 30-day window)
- **SLA** (Service Level Agreement): the contractual commitment with defined penalties if breached; always set SLA below SLO to leave buffer

### Writing a Good SLO

An SLO must specify:
1. The SLI being measured
2. The target percentage
3. The time window (rolling 30 days is standard)
4. What counts as "good" vs "bad" (the success criterion)

Examples:
- "99.9% of payment API requests return HTTP 2xx over a rolling 30-day window"
- "99% of payment API requests complete in under 500ms over a rolling 30-day window"
- "The payment service is reachable from all regions 99.95% of the time over 30 days"

### Availability SLO Math

| SLO | Downtime per year | Downtime per month |
|-----|-------------------|--------------------|
| 99% | 87.6 hours | 7.3 hours |
| 99.9% | 8.7 hours | 43.8 minutes |
| 99.95% | 4.4 hours | 21.9 minutes |
| 99.99% | 52.6 minutes | 4.4 minutes |
| 99.999% | 5.3 minutes | 26 seconds |

Most internal services target 99.9%. Customer-facing critical paths target 99.95%–99.99%. Do not set SLOs higher than you can actually achieve; an SLO you always exceed has no meaning.

### Error Budget Policy

- Error budget = 1 − SLO (e.g., for 99.9% availability, 0.1% of requests can fail over 30 days)
- Track remaining error budget in a Grafana dashboard so teams see how much headroom they have

| Budget consumed | Action |
|-----------------|--------|
| < 50% | Normal — continue shipping |
| 50–75% | Review recent deployments; tighten testing |
| 75–99% | Freeze non-critical deployments; prioritize reliability work |
| 100% (exhausted) | All hands on reliability; no new features until budget recovers |

### Burn Rate Alerting

Burn rate measures how fast you are spending your error budget relative to the expected pace.

- If SLO is 99.9% over 30 days, you have ~43.8 minutes of downtime budget per month
- A burn rate of 1.0 means you are consuming budget at exactly the sustainable rate
- A burn rate of 14x means you will exhaust your monthly budget in ~3 days

```promql
# 1-hour burn rate for a 99.9% SLO
(
  1 - (
    rate(http_requests_total{status=~"2.."}[1h])
    / rate(http_requests_total[1h])
  )
) / (1 - 0.999)
```

Recommended burn rate alerts:

| Burn rate | Window | Severity | Action |
|-----------|--------|----------|--------|
| > 14x | 1 hour | critical | Page immediately |
| > 6x | 6 hours | critical | Page immediately |
| > 3x | 1 day | warning | Ticket — investigate today |
| > 1x | 3 days | warning | Ticket — investigate this week |

---

## Dashboard Design (Grafana)

### Golden Signals Dashboard Template

Every service should have a single dashboard with at minimum four panels, one per golden signal:

1. **Traffic** — request rate (RPS) over time
   ```promql
   sum(rate(http_requests_total{service="$service"}[5m])) by (endpoint)
   ```

2. **Latency** — p50, p95, and p99 response time on one panel
   ```promql
   histogram_quantile(0.99, sum(rate(request_duration_seconds_bucket{service="$service"}[5m])) by (le))
   histogram_quantile(0.95, sum(rate(request_duration_seconds_bucket{service="$service"}[5m])) by (le))
   histogram_quantile(0.50, sum(rate(request_duration_seconds_bucket{service="$service"}[5m])) by (le))
   ```

3. **Errors** — error rate as a percentage of total traffic
   ```promql
   sum(rate(http_requests_total{service="$service",status=~"5.."}[5m]))
   / sum(rate(http_requests_total{service="$service"}[5m]))
   ```

4. **Saturation** — CPU%, memory%, and connection pool usage on one panel
   ```promql
   avg(container_cpu_usage_seconds_total{pod=~"$service.*"}) by (pod)
   ```

### Useful Panel Types

| Type | Best for |
|------|----------|
| Time series | Metrics over time — use for most panels |
| Stat | Single current value (uptime %, current error count) |
| Gauge | Percentage of a max (disk usage, pool utilization) |
| Table | Top N slow endpoints, recent error breakdown by status |
| Heatmap | Latency distribution from a histogram metric |
| Logs panel | Log lines from Loki shown alongside matching metrics |
| Bar chart | Comparison across services or endpoints at a point in time |

### Dashboard Organization Tips

- Add a row per service tier (frontend, API, database, queue)
- Use template variables (`$service`, `$env`, `$region`) so dashboards are reusable
- Link each panel's title to the relevant runbook or alert rule
- Set the default time range to "Last 3 hours" with a 30-second auto-refresh for live debugging
- Pin the error budget remaining as a Stat panel at the top of every service dashboard

---

## Checklist

- [ ] All log lines include timestamp, level, service, trace_id, span_id, and request_id
- [ ] Log level is INFO in production; DEBUG only in development; never log sensitive data
- [ ] Correlation ID is generated at the edge and propagated through all downstream services and async queues
- [ ] RED metrics (rate, errors, duration) are instrumented on every service entry point
- [ ] Prometheus metric labels have low cardinality — no user IDs, order IDs, or raw URL paths
- [ ] Histogram buckets are tuned to the expected latency range of the service
- [ ] OpenTelemetry traces are configured with an OTLP exporter pointing at a collector
- [ ] Context propagation uses the W3C `traceparent` header across all HTTP and gRPC calls
- [ ] Every alert has a `severity` label, a `for:` duration, and a `runbook` annotation
- [ ] SLOs are defined with an explicit SLI, target percentage, and rolling time window
- [ ] Error budget policy is documented: what the team does when 75%, 100% of budget is consumed
- [ ] Grafana dashboard includes all four golden signals (traffic, latency, errors, saturation) with template variables
