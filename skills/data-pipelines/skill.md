---
name: data-pipelines
description: Use when building or debugging data pipelines with Airflow or Prefect, writing dbt models or tests, designing incremental loads, implementing idempotent ETL/ELT jobs, validating data quality, or orchestrating multi-step data workflows.
---

# Data Pipelines

Orchestration, transformation, and validation patterns for production data pipelines.

## When to Activate

- Writing Airflow DAGs, operators, sensors, or XComs
- Building dbt models, sources, tests, or macros
- Designing incremental vs full-load strategies
- Implementing idempotent pipeline runs
- Validating data quality with dbt tests or Great Expectations
- Orchestrating multi-step ELT/ETL workflows
- Debugging failed runs, backfills, or data freshness issues

## ETL vs ELT Decision

| Approach | Transform where | Use when |
|---|---|---|
| **ETL** | Before loading (in pipeline code) | Target warehouse has limited compute; PII must be masked before storage |
| **ELT** | After loading (in warehouse SQL) | Modern warehouse (BigQuery, Snowflake, Redshift); raw data must be preserved |
| **Streaming** | Continuously (Kafka + Flink/Spark) | Sub-minute latency required; event sourcing |

**Default for modern stacks: ELT** — land raw data, transform with dbt, version-control SQL.

## Airflow

### DAG Structure

```python
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

@dag(
    schedule="0 6 * * *",          # 6 AM daily
    start_date=datetime(2026, 1, 1),
    catchup=False,                  # don't backfill missed runs on deploy
    max_active_runs=1,              # prevent overlapping runs
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
        "email_on_failure": True,
    },
    tags=["finance", "daily"],
)
def daily_revenue_pipeline():

    @task
    def extract_orders(execution_date=None) -> list[dict]:
        hook = PostgresHook(postgres_conn_id="source_db")
        # Use execution_date for idempotent extraction
        rows = hook.get_records(
            "SELECT * FROM orders WHERE date = %s",
            parameters=[execution_date.date()],
        )
        return [dict(r) for r in rows]

    @task
    def transform(orders: list[dict]) -> list[dict]:
        return [
            {**o, "revenue_usd": o["amount"] * o["fx_rate"]}
            for o in orders
            if o["status"] == "completed"
        ]

    @task
    def load(records: list[dict], execution_date=None):
        hook = PostgresHook(postgres_conn_id="warehouse")
        # Idempotent: delete-then-insert for the partition date
        hook.run("DELETE FROM daily_revenue WHERE date = %s", parameters=[execution_date.date()])
        hook.insert_rows("daily_revenue", [[r["date"], r["revenue_usd"]] for r in records])

    orders = extract_orders()
    transformed = transform(orders)
    load(transformed)

dag = daily_revenue_pipeline()
```

### Operators & Sensors

```python
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from airflow.sensors.filesystem import FileSensor
from airflow.sensors.sql import SqlSensor
from airflow.providers.http.sensors.http import HttpSensor

# Wait for a file to appear (S3, GCS, local)
wait_for_export = FileSensor(
    task_id="wait_for_export",
    filepath="/data/exports/{{ ds }}/orders.csv",
    poke_interval=60,    # check every 60s
    timeout=3600,        # fail after 1 hour
    mode="reschedule",   # release worker slot while waiting
)

# Wait for upstream table to be populated
wait_for_source = SqlSensor(
    task_id="wait_for_orders",
    conn_id="source_db",
    sql="SELECT COUNT(*) FROM orders WHERE date = '{{ ds }}' HAVING COUNT(*) > 0",
    poke_interval=120,
    mode="reschedule",
)

# Branch: skip load on weekends
def should_load(**context):
    if context["execution_date"].weekday() >= 5:
        return "skip_load"
    return "load"

branch = BranchPythonOperator(task_id="check_day", python_callable=should_load)
```

### XComs — Task Communication

```python
# Push value
@task
def extract() -> dict:
    return {"row_count": 1042, "checksum": "abc123"}  # return value auto-pushes XCom

# Pull value
@task
def validate(stats: dict):   # passed as argument from task dependency
    assert stats["row_count"] > 0, "Empty extract"

# Manual XCom pull (classic operators)
def load(**context):
    stats = context["task_instance"].xcom_pull(task_ids="extract")
    print(stats["row_count"])
```

**XCom limits:** XComs are stored in the Airflow metadata DB — not suited for large data. Pass row counts, checksums, and file paths through XComs; never entire datasets.

### Dynamic Task Mapping

```python
@task
def get_regions() -> list[str]:
    return ["us-east", "eu-west", "ap-south"]

@task
def process_region(region: str):
    extract_and_load(region)

# Creates one task instance per region — parallelized automatically
process_region.expand(region=get_regions())
```

### Connections & Variables

```python
from airflow.hooks.base import BaseHook
from airflow.models import Variable

# Never hardcode credentials — use Connections
conn = BaseHook.get_connection("my_postgres")
dsn = f"postgresql://{conn.login}:{conn.password}@{conn.host}/{conn.schema}"

# Runtime config — use Variables (or better: Airflow Params)
batch_size = int(Variable.get("etl_batch_size", default_var=1000))
```

---

## dbt

### Project Structure

```
dbt_project/
├── models/
│   ├── staging/          # stg_* — raw → typed, renamed, deduplicated
│   │   └── stg_orders.sql
│   ├── intermediate/     # int_* — business logic joins
│   │   └── int_order_items.sql
│   └── marts/            # final — wide tables for BI/downstream
│       └── fct_revenue.sql
├── tests/                # custom SQL tests
├── macros/               # Jinja macros
├── seeds/                # static CSV reference data
└── dbt_project.yml
```

### Model Types & Materializations

```sql
-- staging/stg_orders.sql
-- Materialization: view (cheap, always fresh)
{{ config(materialized='view') }}

SELECT
    order_id::VARCHAR      AS order_id,
    user_id::VARCHAR       AS user_id,
    created_at::TIMESTAMP  AS created_at,
    amount_cents / 100.0   AS amount_usd,
    status
FROM {{ source('raw', 'orders') }}
WHERE status != 'test'
```

```sql
-- marts/fct_revenue.sql
-- Materialization: table (fast reads, rebuilt on each run)
{{ config(materialized='table') }}

SELECT
    DATE_TRUNC('day', o.created_at) AS date,
    p.name                          AS product_name,
    SUM(oi.quantity)                AS units_sold,
    SUM(oi.quantity * oi.unit_price) AS revenue_usd
FROM {{ ref('stg_orders') }}      o    -- ref() creates dependency
JOIN {{ ref('int_order_items') }} oi ON o.order_id = oi.order_id
JOIN {{ ref('stg_products') }}    p  ON oi.product_id = p.product_id
WHERE o.status = 'completed'
GROUP BY 1, 2
```

### Incremental Models

```sql
-- Only process new/updated rows — essential for large tables
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',    -- or 'delete+insert', 'insert_overwrite'
    on_schema_change='append_new_columns',
) }}

SELECT
    order_id,
    user_id,
    amount_usd,
    created_at,
    updated_at
FROM {{ source('raw', 'orders') }}

{% if is_incremental() %}
    -- Only load rows newer than the last run
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

### Sources & Freshness

```yaml
# models/staging/sources.yml
version: 2

sources:
  - name: raw
    database: analytics
    schema: raw_data
    freshness:
      warn_after: {count: 6, period: hour}
      error_after: {count: 24, period: hour}
    loaded_at_field: _loaded_at       # column that holds ingestion timestamp
    tables:
      - name: orders
        description: Raw orders from the transactional database
      - name: products
```

```bash
# Check source freshness in CI
dbt source freshness
```

### dbt Tests

```yaml
# models/staging/stg_orders.yml
version: 2

models:
  - name: stg_orders
    columns:
      - name: order_id
        tests:
          - not_null
          - unique
      - name: status
        tests:
          - accepted_values:
              values: ["pending", "completed", "cancelled", "refunded"]
      - name: user_id
        tests:
          - not_null
          - relationships:
              to: ref('stg_users')
              field: user_id
      - name: amount_usd
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 100000
```

```sql
-- tests/assert_revenue_non_negative.sql — custom SQL test (fails if rows returned)
SELECT date, revenue_usd
FROM {{ ref('fct_revenue') }}
WHERE revenue_usd < 0
```

### Macros

```sql
-- macros/cents_to_dollars.sql
{% macro cents_to_dollars(column_name) %}
    ({{ column_name }} / 100.0)::NUMERIC(10, 2)
{% endmacro %}

-- Usage in a model
SELECT {{ cents_to_dollars('amount_cents') }} AS amount_usd
```

```sql
-- macros/generate_surrogate_key.sql (or use dbt_utils)
{% macro surrogate_key(fields) %}
    MD5(CONCAT_WS('|', {% for f in fields %}COALESCE(CAST({{ f }} AS VARCHAR), ''){% if not loop.last %}, {% endif %}{% endfor %}))
{% endmacro %}
```

### dbt Commands

```bash
dbt run                              # run all models
dbt run --select staging             # run a directory
dbt run --select stg_orders+         # run model and all downstream
dbt run --select +fct_revenue        # run model and all upstream
dbt test                             # run all tests
dbt test --select stg_orders         # test one model
dbt build                            # run + test in dependency order
dbt source freshness                 # check source data freshness
dbt docs generate && dbt docs serve  # generate + serve lineage docs
dbt compile                          # render SQL without running
```

---

## Idempotency Patterns

A pipeline run is **idempotent** if running it twice produces the same result as running it once.

```python
# GOOD: delete-then-insert for a known partition
def load_partition(date: str, records: list[dict]):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM daily_stats WHERE date = :date"),
            {"date": date}
        )
        conn.execute(insert(DailyStats), records)

# GOOD: UPSERT (merge) on unique key
def upsert_orders(records: list[dict]):
    stmt = pg_insert(orders_table).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["order_id"],
        set_={"status": stmt.excluded.status, "updated_at": stmt.excluded.updated_at}
    )
    with engine.begin() as conn:
        conn.execute(stmt)

# BAD: append-only — reruns duplicate data
def load_orders(records):
    engine.execute(insert(orders_table).values(records))  # duplicates on rerun
```

**Airflow idempotency:** Use `{{ ds }}` (execution date, not run date) in all queries. Two runs for the same `ds` must produce the same output.

---

## Incremental Load Strategies

| Strategy | How | Use When |
|---|---|---|
| **Full refresh** | Truncate + reload entire table | Small tables (<1M rows), no CDC |
| **Incremental by timestamp** | `WHERE updated_at > last_run_max` | Source has reliable `updated_at` |
| **Incremental by partition** | Process one date partition per run | Append-only event data |
| **CDC (change data capture)** | Debezium → Kafka → warehouse | High-volume, low-latency, soft deletes |
| **Snapshot** | dbt snapshot (`strategy: timestamp`) | Track slowly-changing dimensions |

```python
# Watermark-based incremental (Python)
def get_watermark(conn, table: str) -> datetime:
    row = conn.execute(
        text("SELECT COALESCE(MAX(updated_at), '1970-01-01') FROM :table", bindparams=[bindparam("table")])
    ).fetchone()
    return row[0]

def extract_incremental(source_conn, watermark: datetime) -> list[dict]:
    return source_conn.execute(
        text("SELECT * FROM orders WHERE updated_at > :wm ORDER BY updated_at"),
        {"wm": watermark},
    ).fetchall()
```

---

## Data Validation

### dbt-native (preferred)

```yaml
# Generic tests: not_null, unique, accepted_values, relationships
# Package tests: dbt_utils, dbt_expectations (Great Expectations style)
- name: amount_usd
  tests:
    - dbt_expectations.expect_column_values_to_be_between:
        min_value: 0
        max_value: 50000
        row_condition: "status = 'completed'"
```

### Python validation (Great Expectations)

```python
import great_expectations as gx

context = gx.get_context()
suite = context.add_expectation_suite("orders_suite")

validator = context.get_validator(
    batch_request=batch_request,
    expectation_suite_name="orders_suite",
)
validator.expect_column_values_to_not_be_null("order_id")
validator.expect_column_values_to_be_unique("order_id")
validator.expect_column_values_to_be_between("amount_usd", min_value=0)
validator.expect_column_pair_values_A_to_be_greater_than_B(
    "completed_at", "created_at"
)

results = validator.validate()
if not results.success:
    raise ValueError(f"Data quality check failed: {results}")
```

### Row-count reconciliation

```python
@task
def reconcile(source_count: int, target_count: int, tolerance: float = 0.001):
    delta = abs(source_count - target_count) / max(source_count, 1)
    if delta > tolerance:
        raise ValueError(
            f"Row count mismatch: source={source_count}, target={target_count}, "
            f"delta={delta:.2%} > {tolerance:.2%} tolerance"
        )
```

---

## Monitoring & Alerting

```python
# Airflow: SLA miss callback
def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    send_slack_alert(f"SLA missed for DAG {dag.dag_id}: {task_list}")

@dag(sla_miss_callback=sla_miss_callback)
def my_dag():
    ...

# Airflow: task-level SLA (fail if task exceeds duration)
load = PythonOperator(
    task_id="load",
    python_callable=load_fn,
    sla=timedelta(minutes=30),   # alert if this task takes >30 min
)
```

```python
# Emit pipeline metrics to Prometheus/StatsD
from airflow.stats import Stats

Stats.incr("pipeline.rows_processed", count=row_count, tags={"dag": dag_id})
Stats.timing("pipeline.duration_ms", value=duration_ms, tags={"dag": dag_id})
```

---

## Red Flags

- **`catchup=True` on a new DAG** — Airflow will try to backfill all missed runs since `start_date`; set `catchup=False` on new DAGs and trigger backfills manually with `airflow dags backfill`
- **Passing datasets through XComs** — XComs are stored in the Airflow metadata DB (SQLite or Postgres); passing DataFrames or large lists corrupts the DB and kills performance; pass file paths, row counts, or checksums only
- **Non-idempotent pipeline** — if a run fails halfway and must be retried, appending duplicates corrupts the target; always upsert or delete-then-insert on a partition key
- **No `updated_at` index on source tables** — incremental loads do `WHERE updated_at > watermark`; without an index this is a full-table scan on every run; ensure the source has an index on the watermark column
- **Hard-coded credentials in DAG code** — DAGs are stored in version control and Airflow logs; always use Airflow Connections or environment variables, never string literals
- **`mode="poke"` on long-waiting sensors** — poke mode holds a worker slot while waiting; use `mode="reschedule"` so the slot is released between checks
- **Unbounded full-refresh on large tables** — a full refresh of a 500M-row table is slow and expensive; use incremental models with `unique_key` + merge strategy once the table exceeds 10M rows
- **No data quality tests before downstream loads** — failing silently and loading bad data is worse than failing loudly; add `dbt test` or row-count reconciliation as a gate before final loads

## Checklist

- [ ] DAG has `catchup=False` and `max_active_runs=1` unless backfill is intended
- [ ] All tasks are idempotent — reruns produce the same result
- [ ] Execution date (`{{ ds }}`) used in queries, not wall-clock time
- [ ] XComs carry only metadata (counts, paths, checksums) — not datasets
- [ ] Airflow Connections used for all credentials — no hardcoded secrets
- [ ] Sensors use `mode="reschedule"` not `mode="poke"`
- [ ] dbt staging models rename, cast, and deduplicate raw source data
- [ ] `ref()` used for all cross-model dependencies — never hardcoded table names
- [ ] Incremental models have `unique_key` and handle late-arriving data
- [ ] Source freshness checks configured and run in CI (`dbt source freshness`)
- [ ] dbt tests cover: `not_null`, `unique`, `accepted_values`, `relationships` on key columns
- [ ] Row-count reconciliation between source and target after each load
- [ ] SLA alerts configured for critical DAGs
- [ ] Backfill procedure documented and tested

> See also: `database-design` (index design, query optimization, migration patterns)
> See also: `observability` (structured logging, metrics, SLO alerting for pipeline health)
