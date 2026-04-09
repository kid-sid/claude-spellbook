---
name: performance-testing
description: Performance and load testing: test type selection (load/stress/soak/spike/volume), k6 script patterns (stages, thresholds, scenarios), Locust HttpUser task weighting, Go benchmark functions with benchstat, SLO-based pass/fail criteria, bottleneck identification, and CI integration.
---

# Performance Testing

Load and performance testing validates that your system meets latency and throughput requirements under realistic and extreme traffic conditions.

## When to Activate

- Load testing an API before a product launch
- Setting up k6 or Locust for a project
- Writing Go benchmark functions for critical code paths
- Defining SLO-based pass/fail thresholds for load tests
- Identifying bottlenecks under load (pool exhaustion, N+1, GC pressure)
- Adding performance regression detection to a CI/CD pipeline

## Test Type Decision Table

| Type | Description | Load shape | Goal | When to run |
|------|-------------|-----------|------|-------------|
| Load | Simulate expected traffic | Ramp to normal, hold | Verify baseline meets SLO | Pre-launch, nightly |
| Stress | Push beyond capacity | Ramp past normal | Find breaking point | Before scaling decisions |
| Soak | Sustained load over time | Constant for 1–4 hours | Detect memory leaks, pool exhaustion | Weekly |
| Spike | Sudden burst | 0 → peak instantly | Test autoscaling, queue buffering | Before planned events |
| Volume | Large datasets, normal load | Normal rps, huge data | Find data-size bottlenecks | When data volume increases |

## k6

### Script Structure

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const paymentDuration = new Trend('payment_duration');

export const options = {
  stages: [
    { duration: '2m', target: 50 },   // ramp up
    { duration: '5m', target: 50 },   // hold
    { duration: '2m', target: 100 },  // ramp up further
    { duration: '5m', target: 100 },  // hold
    { duration: '2m', target: 0 },    // ramp down
  ],
  thresholds: {
    // SLO-based pass/fail: test fails if these are breached
    'http_req_duration': ['p(95)<500', 'p(99)<1000'],
    'http_req_failed':   ['rate<0.01'],
    'errors':            ['rate<0.05'],
  },
};

export default function () {
  const res = http.post(
    'https://api.example.com/payments',
    JSON.stringify({ amount: 100, currency: 'USD' }),
    {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${__ENV.API_TOKEN}`,
      },
    }
  );

  const ok = check(res, {
    'status is 201':          (r) => r.status === 201,
    'response time < 500ms':  (r) => r.timings.duration < 500,
  });

  errorRate.add(!ok);
  paymentDuration.add(res.timings.duration);
  sleep(1);  // think time between requests
}
```

### Scenarios (Mixed Workloads)

```javascript
export const options = {
  scenarios: {
    browse: {
      executor: 'constant-vus',
      vus: 100,
      duration: '10m',
      exec: 'browseProducts',
    },
    checkout: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      stages: [{ duration: '5m', target: 50 }],
      preAllocatedVUs: 60,
      exec: 'checkout',
    },
  },
};

export function browseProducts() { /* ... */ }
export function checkout() { /* ... */ }
```

### Running k6

```bash
k6 run script.js
k6 run --vus 100 --duration 10m script.js

# Export to InfluxDB + Grafana for dashboards
k6 run --out influxdb=http://localhost:8086/k6 script.js

# Cloud execution
k6 cloud script.js
```

## Locust (Python)

```python
from locust import HttpUser, task, between

class PaymentUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Called once per VU — authenticate"""
        res = self.client.post('/auth/token', json={
            'email': 'test@example.com',
            'password': 'password',
        })
        self.token = res.json()['access_token']

    @task(3)  # weight 3: 3× more frequent than weight-1 tasks
    def browse_products(self):
        with self.client.get(
            '/products',
            headers=self._auth(),
            name='/products',          # group dynamic URLs
            catch_response=True,
        ) as res:
            if res.status_code != 200:
                res.failure(f"Got {res.status_code}")

    @task(1)
    def create_payment(self):
        self.client.post(
            '/payments',
            json={'amount': 100},
            headers=self._auth(),
        )

    def _auth(self):
        return {'Authorization': f'Bearer {self.token}'}
```

```bash
# Headless CI mode
locust -f locustfile.py \
  --headless -u 100 -r 10 --run-time 5m \
  --host https://api.example.com \
  --csv results          # outputs results_stats.csv, results_failures.csv
```

## Go Benchmarks

```go
package payment_test

import (
    "fmt"
    "testing"
)

func BenchmarkProcessPayment(b *testing.B) {
    svc := NewPaymentService(testDB)
    b.ResetTimer()   // don't count setup time
    b.ReportAllocs() // show allocations/op in output

    for i := 0; i < b.N; i++ {
        _, err := svc.ProcessPayment(ctx, Payment{Amount: 100})
        if err != nil {
            b.Fatal(err)
        }
    }
}

// Sub-benchmarks for different scenarios
func BenchmarkProcessPayment_Sizes(b *testing.B) {
    for _, amount := range []float64{1, 100, 10_000} {
        b.Run(fmt.Sprintf("amount=%.0f", amount), func(b *testing.B) {
            for i := 0; i < b.N; i++ {
                svc.ProcessPayment(ctx, Payment{Amount: amount})
            }
        })
    }
}
```

```bash
# Run benchmarks
go test -bench=. -benchmem -benchtime=10s ./...
# Output: BenchmarkProcessPayment-8  50000  23456 ns/op  1024 B/op  12 allocs/op

# Compare before/after a change
go test -bench=. -count=10 -benchmem ./... > before.txt
# ... make the change ...
go test -bench=. -count=10 -benchmem ./... > after.txt
benchstat before.txt after.txt
```

## SLO-Based Pass/Fail Criteria

### Defining Thresholds from SLOs

Base thresholds on your production SLOs — not arbitrary numbers.

```javascript
// If SLO: p99 < 500ms, error rate < 0.1%
thresholds: {
  'http_req_duration': ['p(50)<100', 'p(95)<300', 'p(99)<500'],
  'http_req_failed':   ['rate<0.001'],
}
```

### Establishing a Baseline

1. Run load test against staging with production-like traffic shape
2. Record p50 / p95 / p99 and error rate
3. Set regression threshold: fail if p99 degrades > 20% from baseline
4. Set SLO threshold: fail if p99 exceeds SLO target

### Bottleneck Identification Under Load

| Symptom | Likely cause | How to confirm | Fix |
|---------|-------------|---------------|-----|
| Latency climbs with VU count | Connection pool exhausted | Check pool wait metric | Increase pool / add PgBouncer |
| Error spikes at N rps | Thread / goroutine limit | Check active connections | Tune concurrency config |
| Memory grows during soak | Memory leak / large cache | Heap profile during test | Fix leak, tune GC |
| High latency, low CPU | N+1 queries | Count DB queries per request | Add eager loading |
| CPU > 90% | Compute bottleneck | CPU flame graph | Optimize hot path, add cache |
| Latency spikes periodically | GC pause (JVM/Go) | GC log analysis | Tune GC, reduce allocations |

## CI Integration

### When to Run

| Type | Frequency | Trigger | Failure action |
|------|-----------|---------|---------------|
| Smoke perf (5 VUs, 1 min) | Every PR | PR CI | Fail PR if p99 > 2× baseline |
| Full load test | Nightly | Cron | Alert on Slack |
| Stress test | Weekly | Cron | Report only |

### GitHub Actions Example

```yaml
jobs:
  load-test:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    steps:
      - uses: actions/checkout@v4

      - name: Run k6 load test
        uses: grafana/k6-action@v0.3.0
        with:
          filename: tests/load/payment.js
        env:
          API_TOKEN: ${{ secrets.LOAD_TEST_TOKEN }}
          K6_CLOUD_TOKEN: ${{ secrets.K6_CLOUD_TOKEN }}

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: k6-results-${{ github.run_id }}
          path: results/
```

> See also: `performance`, `observability`, `ci-cd`

## Checklist

- [ ] Test type chosen (load/stress/soak/spike) matches the specific question being answered
- [ ] k6 / Locust thresholds tied to SLO values — not made-up numbers
- [ ] Baseline measured before setting regression thresholds
- [ ] Test users and data isolated from production
- [ ] Think time (`sleep`) included in VU scripts for realistic simulation
- [ ] k6 `check()` used for per-request assertions (not just global thresholds)
- [ ] Go benchmarks include `b.ReportAllocs()` and `b.ResetTimer()`
- [ ] `benchstat` used to compare before/after for Go performance changes
- [ ] Bottleneck identification checklist followed when tests fail
- [ ] Load test results stored as CI artifacts for trending over time
