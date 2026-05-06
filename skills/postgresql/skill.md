---
name: postgresql
description: Use when writing complex PostgreSQL queries, diagnosing slow queries with EXPLAIN ANALYZE, designing indexes, handling concurrent writes, or planning safe schema migrations on large tables.
---

# PostgreSQL Patterns

Advanced querying, indexing, and schema design for PostgreSQL 14+.

## When to Activate

- Writing window functions, CTEs, or recursive queries
- Querying JSONB columns
- Designing indexes or diagnosing missing indexes
- Interpreting `EXPLAIN ANALYZE` output
- Handling concurrent writes (upsert, locking, transactions)
- Full-text search without Elasticsearch
- Planning schema migrations safely

---

## Window Functions

Window functions compute values across rows related to the current row — without collapsing them like `GROUP BY`.

```sql
-- ROW_NUMBER: unique rank per partition
SELECT
  user_id,
  order_id,
  total,
  ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn
FROM orders;

-- Get each user's latest order
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn
  FROM orders
) ranked
WHERE rn = 1;

-- RANK vs DENSE_RANK vs ROW_NUMBER
-- RANK:       1,2,2,4   (gaps after tie)
-- DENSE_RANK: 1,2,2,3   (no gaps)
-- ROW_NUMBER: 1,2,3,4   (always unique)

-- Running total
SELECT
  date,
  amount,
  SUM(amount) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
FROM transactions;

-- Moving average (last 7 days)
SELECT
  date,
  value,
  AVG(value) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7
FROM metrics;

-- LAG/LEAD: access previous/next row
SELECT
  date,
  revenue,
  LAG(revenue)  OVER (ORDER BY date) AS prev_revenue,
  LEAD(revenue) OVER (ORDER BY date) AS next_revenue,
  revenue - LAG(revenue) OVER (ORDER BY date) AS day_over_day
FROM daily_revenue;

-- NTILE: divide rows into buckets
SELECT user_id, spend,
  NTILE(4) OVER (ORDER BY spend DESC) AS quartile  -- 1=top 25%
FROM user_spend;
```

---

## CTEs (Common Table Expressions)

```sql
-- Basic CTE — improves readability, reuse within query
WITH active_users AS (
  SELECT id, name, email
  FROM users
  WHERE status = 'active' AND last_login > NOW() - INTERVAL '30 days'
),
user_orders AS (
  SELECT user_id, COUNT(*) AS order_count, SUM(total) AS lifetime_value
  FROM orders
  WHERE status = 'completed'
  GROUP BY user_id
)
SELECT
  u.name,
  u.email,
  COALESCE(o.order_count, 0) AS orders,
  COALESCE(o.lifetime_value, 0) AS ltv
FROM active_users u
LEFT JOIN user_orders o ON u.id = o.user_id
ORDER BY o.lifetime_value DESC NULLS LAST;

-- Recursive CTE — hierarchies, trees, paths
WITH RECURSIVE category_tree AS (
  -- Anchor: start from roots
  SELECT id, name, parent_id, 0 AS depth, ARRAY[id] AS path
  FROM categories
  WHERE parent_id IS NULL

  UNION ALL

  -- Recursive: join children
  SELECT c.id, c.name, c.parent_id, ct.depth + 1, ct.path || c.id
  FROM categories c
  INNER JOIN category_tree ct ON c.parent_id = ct.id
)
SELECT * FROM category_tree ORDER BY path;

-- Writable CTEs (INSERT/UPDATE/DELETE in CTE)
WITH deleted_sessions AS (
  DELETE FROM sessions
  WHERE expires_at < NOW()
  RETURNING user_id, session_id
)
INSERT INTO audit_log (user_id, action, metadata)
SELECT user_id, 'session_expired', jsonb_build_object('session_id', session_id)
FROM deleted_sessions;
```

---

## JSONB

JSONB stores JSON as binary — indexable and queryable.

```sql
-- Schema
CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Query operators
SELECT payload->>'email'          FROM users;          -- text (->>' extracts as text)
SELECT payload->'address'         FROM users;          -- JSONB subtree
SELECT payload#>>'{address,city}' FROM users;          -- nested path as text
SELECT payload#>'{address}'       FROM users;          -- nested path as JSONB

-- Filter on JSONB fields
SELECT * FROM events WHERE payload->>'type' = 'purchase';
SELECT * FROM events WHERE (payload->>'amount')::numeric > 100;
SELECT * FROM events WHERE payload @> '{"status": "active"}';  -- contains
SELECT * FROM events WHERE payload ? 'discount_code';           -- key exists
SELECT * FROM events WHERE payload ?| ARRAY['tag1', 'tag2'];    -- any key exists
SELECT * FROM events WHERE payload ?& ARRAY['tag1', 'tag2'];    -- all keys exist

-- Update JSONB
UPDATE users
SET metadata = jsonb_set(metadata, '{last_login}', to_jsonb(NOW()))
WHERE id = '123';

-- Remove key
UPDATE users SET metadata = metadata - 'temp_token' WHERE id = '123';

-- Aggregate into JSONB
SELECT jsonb_agg(row_to_json(u)) FROM users u WHERE active;
SELECT jsonb_object_agg(key, value) FROM settings;

-- Unnest JSONB array
SELECT elem->>'name' FROM products, jsonb_array_elements(tags) AS elem;
```

---

## Indexes

### B-tree (default — equality and range)

```sql
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);

-- Composite: order matters — put equality columns first, range last
CREATE INDEX idx_orders_user_status_date ON orders(user_id, status, created_at);
-- This index helps: WHERE user_id = ? AND status = ? AND created_at > ?
-- This index helps: WHERE user_id = ? AND status = ?
-- This index doesn't help much: WHERE status = ? AND created_at > ?  (skipped user_id)
```

### Partial index — index only matching rows

```sql
-- Index only active orders — much smaller than full index
CREATE INDEX idx_active_orders ON orders(user_id, created_at)
WHERE status = 'active';

-- Index only non-null values
CREATE INDEX idx_users_stripe_id ON users(stripe_customer_id)
WHERE stripe_customer_id IS NOT NULL;
```

### Covering index — include extra columns to avoid heap fetches

```sql
-- Query: SELECT status, total FROM orders WHERE user_id = ?
-- Without INCLUDE: index lookup + heap fetch for status, total
-- With INCLUDE: index lookup only (index-only scan)
CREATE INDEX idx_orders_user_covering ON orders(user_id) INCLUDE (status, total);
```

### GIN — full-text search and JSONB

```sql
-- JSONB containment queries (@>, ?)
CREATE INDEX idx_events_payload ON events USING GIN (payload);

-- Full-text search
CREATE INDEX idx_articles_tsv ON articles USING GIN (
  to_tsvector('english', title || ' ' || body)
);
```

### Expression index

```sql
-- Query: WHERE lower(email) = ?
CREATE INDEX idx_users_email_lower ON users (lower(email));

-- Query: WHERE DATE(created_at) = ?
CREATE INDEX idx_orders_date ON orders (DATE(created_at));
```

---

## EXPLAIN ANALYZE

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT ...;
```

Key things to look for:

```
-- GOOD: index scan
Index Scan using idx_orders_user_id on orders  (cost=0.43..8.45 rows=1)
  Index Cond: (user_id = '123')
  Actual Rows: 1, Loops: 1

-- BAD: sequential scan on large table
Seq Scan on orders  (cost=0.00..45000.00 rows=1000000)   ← missing index
  Filter: (user_id = '123')
  Rows Removed by Filter: 999999

-- BAD: nested loop with many iterations
Nested Loop  (rows=10000)
  -> Seq Scan on orders         ← no index on join column
  -> Index Scan using ...

-- Check Buffers output for cache hit ratio
Buffers: shared hit=95 read=5    ← 95% from cache (good)
Buffers: shared hit=10 read=990  ← mostly disk reads (bad — consider index or caching)
```

**Workflow:** run `EXPLAIN ANALYZE`, look for `Seq Scan` on large tables and `Rows Removed by Filter` ratios. Add index on the filter/join column, re-check.

---

## Transactions and Locking

```sql
-- Explicit transaction
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 'A';
UPDATE accounts SET balance = balance + 100 WHERE id = 'B';
COMMIT;   -- or ROLLBACK;

-- SELECT FOR UPDATE — lock rows to prevent concurrent modification
BEGIN;
SELECT * FROM inventory WHERE product_id = '123' FOR UPDATE;
-- Other transactions block here until we COMMIT
UPDATE inventory SET quantity = quantity - 1 WHERE product_id = '123';
COMMIT;

-- SELECT FOR UPDATE SKIP LOCKED — skip locked rows (job queue pattern)
SELECT * FROM jobs
WHERE status = 'pending'
ORDER BY created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;

-- Isolation levels
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;    -- default
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;   -- no phantom reads within tx
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;      -- full serialization (slowest)

-- Advisory locks — application-level named locks
SELECT pg_advisory_lock(12345);       -- session lock
SELECT pg_advisory_xact_lock(12345);  -- transaction lock (auto-released on commit)
```

---

## Upsert (INSERT ... ON CONFLICT)

```sql
-- Insert or ignore
INSERT INTO user_preferences (user_id, key, value)
VALUES ('123', 'theme', 'dark')
ON CONFLICT (user_id, key) DO NOTHING;

-- Insert or update
INSERT INTO user_preferences (user_id, key, value, updated_at)
VALUES ('123', 'theme', 'dark', NOW())
ON CONFLICT (user_id, key)
DO UPDATE SET
  value = EXCLUDED.value,
  updated_at = EXCLUDED.updated_at;

-- Conditional upsert — only update if new value is newer
ON CONFLICT (id) DO UPDATE SET
  value = EXCLUDED.value
WHERE user_preferences.updated_at < EXCLUDED.updated_at;
```

---

## LATERAL Joins

LATERAL lets a subquery reference columns from tables to its left — like a correlated subquery but returning multiple rows.

```sql
-- Latest 3 orders per user
SELECT u.name, o.order_id, o.total
FROM users u
CROSS JOIN LATERAL (
  SELECT order_id, total
  FROM orders
  WHERE user_id = u.id          -- references u from outer query
  ORDER BY created_at DESC
  LIMIT 3
) o;

-- Useful with functions that return sets
SELECT u.id, tags.tag
FROM users u
CROSS JOIN LATERAL jsonb_array_elements_text(u.tags) AS tags(tag);
```

---

## Full-Text Search

```sql
-- tsvector: preprocessed searchable document
-- tsquery: search query with operators

-- Create a generated column (auto-updated)
ALTER TABLE articles ADD COLUMN search_vector tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(title,'') || ' ' || coalesce(body,''))
  ) STORED;

CREATE INDEX idx_articles_search ON articles USING GIN (search_vector);

-- Search
SELECT title, ts_rank(search_vector, query) AS rank
FROM articles, to_tsquery('english', 'postgres & indexing') query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 10;

-- Highlight matching terms
SELECT ts_headline('english', body, to_tsquery('postgres & indexing'),
  'StartSel=<mark>, StopSel=</mark>, MaxFragments=2'
) FROM articles;

-- Phrase search (words in order)
SELECT * FROM articles
WHERE search_vector @@ phraseto_tsquery('english', 'full text search');
```

---

## Migration Strategy

```sql
-- Safe for large tables (doesn't lock):

-- 1. Add nullable column first (no default needed, no lock)
ALTER TABLE orders ADD COLUMN shipped_at TIMESTAMPTZ;

-- 2. Backfill in batches (avoid one giant UPDATE that locks)
UPDATE orders SET shipped_at = completed_at
WHERE id IN (SELECT id FROM orders WHERE shipped_at IS NULL LIMIT 10000);
-- Repeat until done, or use pg_cron / application loop

-- 3. Add constraint after backfill
ALTER TABLE orders ALTER COLUMN shipped_at SET NOT NULL;

-- Add index concurrently — no table lock
CREATE INDEX CONCURRENTLY idx_orders_shipped_at ON orders(shipped_at);

-- Drop index concurrently
DROP INDEX CONCURRENTLY idx_old_index;

-- Rename column (instant)
ALTER TABLE orders RENAME COLUMN old_name TO new_name;
```

---

## Useful Functions

```sql
-- Date/time
NOW()                             -- current timestamp with timezone
CURRENT_DATE                      -- today as date
DATE_TRUNC('week', created_at)    -- truncate to week start
created_at + INTERVAL '7 days'    -- date arithmetic
EXTRACT(EPOCH FROM duration)      -- seconds as number

-- String
COALESCE(field, 'default')        -- first non-null
NULLIF(field, '')                 -- null if empty string
CONCAT_WS(', ', a, b, c)          -- join with separator, skips nulls
REGEXP_REPLACE(text, pattern, replacement, 'g')
LEFT(text, 100)                   -- first 100 chars

-- Array
ARRAY_AGG(id ORDER BY created_at) -- aggregate into array
UNNEST(tags)                      -- expand array to rows
array_length(tags, 1)             -- length of 1-dimensional array

-- UUID
gen_random_uuid()                 -- generate UUID v4 (pg 13+)
```

---

## Red Flags

- **Missing index on foreign key columns** — PostgreSQL does not auto-index FK columns; every `child(parent_id)` that appears in a `JOIN` or `WHERE` needs a manual `CREATE INDEX`, or every lookup is a sequential scan
- **`CREATE INDEX` without `CONCURRENTLY` on a live table** — plain `CREATE INDEX` acquires a full table lock and blocks all writes for the duration; always use `CREATE INDEX CONCURRENTLY` in production migrations
- **Single giant `UPDATE` to backfill a new column** — `UPDATE orders SET shipped_at = ...` on millions of rows locks the table and blocks production traffic; backfill in batches of 10–50k rows via a loop or pg_cron
- **`EXPLAIN` without `ANALYZE` and `BUFFERS`** — `EXPLAIN` shows estimated costs only; `EXPLAIN (ANALYZE, BUFFERS)` shows actual row counts, actual time, and cache hit ratios — always use both flags when diagnosing performance
- **`SELECT *` on large tables in joins** — selecting all columns brings unnecessary data from disk and prevents index-only scans; always project only the columns you need
- **N+1 queries in application code** — fetching a list then querying for each row's related data in a loop is O(n) round trips; use a single `JOIN` or a single `IN` query with application-side grouping
- **`NOT IN` with a subquery that can return NULLs** — if the subquery returns any `NULL`, `NOT IN` returns no rows at all due to three-valued logic; use `NOT EXISTS` or `LEFT JOIN ... WHERE right.id IS NULL` instead

## Checklist

- [ ] Foreign key columns have indexes (`CREATE INDEX ON child(parent_id)`)
- [ ] Composite indexes put equality columns first, range columns last
- [ ] `EXPLAIN ANALYZE` run on any query returning > 10k rows
- [ ] Partial indexes used for queries with constant `WHERE` conditions
- [ ] Concurrent DDL (`CREATE INDEX CONCURRENTLY`, batched `UPDATE`) for large tables
- [ ] `ON CONFLICT` used for upsert instead of SELECT then INSERT/UPDATE
- [ ] `FOR UPDATE SKIP LOCKED` for queue patterns instead of application-level locking
- [ ] JSONB columns have GIN index when used with `@>` or `?` operators
- [ ] Migrations add nullable column → backfill → add NOT NULL (never the reverse)
