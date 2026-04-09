---
name: database-design
description: "Relational database design: normalization (1NF–3NF), schema naming conventions, primary key strategies, indexing (B-tree, GIN, composite, partial), query optimization with EXPLAIN ANALYZE, zero-downtime migration patterns, and connection pooling. PostgreSQL-focused with Alembic, Prisma, and golang-migrate examples."
---

# Database Design

A practical reference for designing, indexing, migrating, and operating relational databases in production, with PostgreSQL as the primary target.

## When to Activate

- Designing a new database schema or data model
- Adding indexes to improve query performance
- Writing or reviewing a database migration
- Optimizing a slow SQL query
- Choosing between normalization and denormalization strategies
- Setting up connection pooling for a service
- Planning a zero-downtime schema change in production

---

## Schema Design Principles

### Normalization

**First Normal Form (1NF)** — atomic values, no repeating groups.

```sql
-- BAD: repeating groups in a single column
CREATE TABLE orders (
    id        BIGSERIAL PRIMARY KEY,
    user_id   BIGINT NOT NULL,
    item_ids  TEXT NOT NULL  -- "1,2,3" stored as a string
);

-- GOOD: each value gets its own row
CREATE TABLE orders (
    id      BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL
);

CREATE TABLE order_items (
    id         BIGSERIAL PRIMARY KEY,
    order_id   BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id)
);
```

**Second Normal Form (2NF)** — no partial dependencies on a composite key. Every non-key column must depend on the whole key, not just part of it.

```sql
-- BAD: composite key (order_id, product_id), but product_name depends only on product_id
CREATE TABLE order_items (
    order_id     BIGINT NOT NULL,
    product_id   BIGINT NOT NULL,
    product_name TEXT NOT NULL,   -- partial dependency: only on product_id
    quantity     INT  NOT NULL,
    PRIMARY KEY (order_id, product_id)
);

-- GOOD: move product_name to the products table
CREATE TABLE products (
    id   BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE order_items (
    order_id   BIGINT NOT NULL,
    product_id BIGINT NOT NULL REFERENCES products(id),
    quantity   INT NOT NULL,
    PRIMARY KEY (order_id, product_id)
);
```

**Third Normal Form (3NF)** — no transitive dependencies. Non-key columns must not depend on other non-key columns.

```sql
-- BAD: zip_code -> city is a transitive dependency; city is not a key
CREATE TABLE users (
    id       BIGSERIAL PRIMARY KEY,
    name     TEXT NOT NULL,
    zip_code VARCHAR(10),
    city     TEXT          -- city depends on zip_code, not on id
);

-- GOOD: extract the transitive dependency into its own table
CREATE TABLE zip_codes (
    zip_code VARCHAR(10) PRIMARY KEY,
    city     TEXT NOT NULL,
    state    CHAR(2) NOT NULL
);

CREATE TABLE users (
    id       BIGSERIAL PRIMARY KEY,
    name     TEXT NOT NULL,
    zip_code VARCHAR(10) REFERENCES zip_codes(zip_code)
);
```

**Deliberate denormalization** — acceptable in specific scenarios; always document the reason.

| Scenario | Denormalization Pattern | Document as |
|---|---|---|
| Reporting / analytics tables | Pre-aggregated summary columns | `-- DENORM: avoids JOIN on reporting queries` |
| Heavy read workload | Duplicated display name on child table | `-- DENORM: read:write ratio > 100:1` |
| Caching aggregates | `total_order_count` on `users` table | `-- DENORM: updated by trigger, cache of COUNT(orders)` |

---

### Primary Key Strategies

| Strategy | Type | Pros | Cons | Best For |
|---|---|---|---|---|
| `BIGSERIAL` / auto-increment | 8-byte integer | Simple, small, ordered, fast joins | Leaks row count; bad for distributed inserts | Single-database apps, internal IDs |
| UUID v4 | 16-byte random | Globally unique, no ordering | Index fragmentation, 16 bytes, not sortable | Distributed systems (legacy) |
| UUID v7 | 16-byte time-ordered | Globally unique, time-sortable, B-tree friendly | Slightly larger than integer | New distributed systems (preferred) |
| Natural key | Varies | Human-readable, no surrogate needed | Hard to change; rarely truly immutable | ISO country codes, currency codes |

Use `BIGSERIAL` for most tables. Prefer UUID v7 over UUID v4 for distributed or externally-exposed IDs.

```sql
-- BIGSERIAL
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY
);

-- UUID v7 (requires pg_uuidv7 extension or application-generated)
CREATE EXTENSION IF NOT EXISTS "pg_uuidv7";

CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7()
);
```

---

### Data Type Selection

| Use Case | Preferred Type | Avoid | Reason |
|---|---|---|---|
| Short text | `VARCHAR(n)` or `TEXT` | `CHAR(n)` | `CHAR` pads with spaces, wastes storage |
| Timestamps | `TIMESTAMPTZ` | `TIMESTAMP` | `TIMESTAMP` has no timezone — silent bugs in multi-region apps |
| Money / currency | `NUMERIC(10,2)` | `FLOAT` / `DOUBLE PRECISION` | Floating point errors accumulate in financial calculations |
| Semi-structured data | `JSONB` | `JSON` | `JSONB` is binary, indexed, and faster to query |
| Boolean | `BOOLEAN` | `INT` (0/1) | Semantic clarity; `BOOLEAN` accepts `TRUE`/`FALSE`/`NULL` |
| Enums | Lookup table or `TEXT CHECK` | PostgreSQL `ENUM` type | `ENUM` requires `ALTER TYPE` to add values; lookup tables are easier to extend |

```sql
-- BAD: float for money, timestamp without timezone, int for boolean
CREATE TABLE invoices (
    id         SERIAL PRIMARY KEY,
    amount     FLOAT,                     -- BAD: floating point
    created_at TIMESTAMP,                 -- BAD: no timezone
    is_paid    INT DEFAULT 0              -- BAD: use BOOLEAN
);

-- GOOD
CREATE TABLE invoices (
    id         BIGSERIAL PRIMARY KEY,
    amount     NUMERIC(12,2) NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_paid    BOOLEAN      NOT NULL DEFAULT FALSE
);
```

---

## Naming Conventions

- Tables: `snake_case`, plural — `users`, `order_items`, `audit_logs`
- Columns: `snake_case`, singular — `user_id`, `created_at`, `is_active`
- Foreign keys: `<referenced_table_singular>_id` — `user_id` references `users(id)`
- Indexes: `idx_<table>_<columns>` — `idx_users_email`, `idx_orders_user_id_created_at`
- Unique constraints: `uq_<table>_<col>` — `uq_users_email`
- Foreign key constraints: `fk_<table>_<referenced>` — `fk_orders_users`
- Check constraints: `ck_<table>_<rule>` — `ck_products_price_positive`

```sql
CREATE TABLE orders (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT        NOT NULL,
    total      NUMERIC(12,2) NOT NULL,
    created_at TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_orders_users        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT ck_orders_total_pos    CHECK (total >= 0)
);

CREATE UNIQUE INDEX uq_users_email    ON users (email);
CREATE        INDEX idx_orders_user_id ON orders (user_id);
```

---

## Relationships and Foreign Keys

### One-to-Many

The "many" side holds the foreign key column.

```sql
CREATE TABLE posts (
    id         BIGSERIAL    PRIMARY KEY,
    user_id    BIGINT       NOT NULL,
    title      TEXT         NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_posts_users FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE
);
```

**Cascade options:**

| ON DELETE Behavior | When to Use |
|---|---|
| `CASCADE` | Child rows are meaningless without the parent (e.g., post comments deleted when post is deleted) |
| `SET NULL` | Child row survives but loses its association (e.g., assigned user deleted, task becomes unassigned) |
| `RESTRICT` | Prevent deletion of parent if children exist — use when you want explicit cleanup | 
| `NO ACTION` | Same as `RESTRICT` but deferred; default if unspecified — almost always specify explicitly |

---

### Many-to-Many

Use a junction table with a composite primary key. Always include `created_at`.

```sql
CREATE TABLE user_roles (
    user_id    BIGINT      NOT NULL,
    role_id    BIGINT      NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (user_id, role_id),

    CONSTRAINT fk_user_roles_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_roles_roles FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
);
```

Adding `created_at` costs nothing and you will always want it when auditing membership changes.

---

### Polymorphic Associations

**Anti-pattern** — using `entity_type` + `entity_id` with a single generic foreign key column breaks referential integrity because PostgreSQL cannot enforce a foreign key across multiple tables.

```sql
-- BAD: no FK enforcement, fragile JOIN logic
CREATE TABLE comments (
    id          BIGSERIAL PRIMARY KEY,
    entity_type TEXT   NOT NULL, -- 'post' | 'photo' | 'video'
    entity_id   BIGINT NOT NULL, -- could reference any table
    body        TEXT   NOT NULL
);

-- No FK here — the database has no idea what entity_id points to.
```

**Preferred pattern** — separate join tables per entity type, each with a proper foreign key.

```sql
-- GOOD: separate relationship tables, full FK enforcement
CREATE TABLE post_comments (
    id         BIGSERIAL PRIMARY KEY,
    post_id    BIGINT NOT NULL REFERENCES posts(id)   ON DELETE CASCADE,
    body       TEXT   NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE photo_comments (
    id         BIGSERIAL PRIMARY KEY,
    photo_id   BIGINT NOT NULL REFERENCES photos(id)  ON DELETE CASCADE,
    body       TEXT   NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Indexing Strategy

### Index Types

| Type | When to Use | PostgreSQL Syntax |
|---|---|---|
| B-tree | Equality and range queries; default for most columns | `CREATE INDEX idx_name ON tbl (col)` |
| Hash | Equality-only predicates; slightly faster than B-tree for equality | `CREATE INDEX idx_name ON tbl USING HASH (col)` |
| GIN | JSONB fields, arrays, full-text search (`tsvector`) | `CREATE INDEX idx_name ON tbl USING GIN (col)` |
| GiST | Geometric data, PostGIS, range types (`tsrange`, `int4range`) | `CREATE INDEX idx_name ON tbl USING GIST (col)` |
| Partial | Index a filtered subset of rows | `CREATE INDEX idx_name ON tbl (col) WHERE condition` |

```sql
-- B-tree (default): range query on created_at
CREATE INDEX CONCURRENTLY idx_orders_created_at ON orders (created_at);

-- GIN: query inside JSONB column
CREATE INDEX CONCURRENTLY idx_events_payload ON events USING GIN (payload);

-- Partial: only index active (non-deleted) rows
CREATE INDEX CONCURRENTLY idx_users_email_active ON users (email)
    WHERE deleted_at IS NULL;

-- Full-text search
CREATE INDEX CONCURRENTLY idx_articles_fts ON articles USING GIN (to_tsvector('english', title || ' ' || body));
```

---

### Composite Index Column Order

**Rule:** put equality predicate columns first, range predicate columns last.

```sql
-- Query: WHERE tenant_id = $1 AND created_at > $2 ORDER BY created_at DESC

-- BAD: range column first — tenant_id predicate cannot use the index efficiently
CREATE INDEX idx_orders_bad ON orders (created_at, tenant_id);

-- GOOD: equality column first, then range column
CREATE INDEX idx_orders_tenant_created ON orders (tenant_id, created_at);
```

**Covering index** — include non-key columns with `INCLUDE` to avoid a heap fetch (index-only scan).

```sql
-- Without INCLUDE: index scan + heap fetch for each row to retrieve status
CREATE INDEX idx_orders_user ON orders (user_id, created_at);

-- With INCLUDE: index-only scan if status is the only extra column needed
CREATE INDEX idx_orders_user_covering ON orders (user_id, created_at)
    INCLUDE (status, total);
```

---

### Index Bloat

```sql
-- Check index bloat with pgstattuple (requires extension)
CREATE EXTENSION IF NOT EXISTS pgstattuple;

SELECT * FROM pgstatindex('idx_orders_user_id');
-- free_percent > 30 is a sign of bloat worth addressing

-- Rebuild index without locking (safe for production)
REINDEX INDEX CONCURRENTLY idx_orders_user_id;

-- Find unused indexes (zero scans since last stats reset)
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;
```

Unused indexes slow down writes and waste storage. Drop them after confirming they have had zero scans across multiple stats reset periods.

---

## Query Optimization with EXPLAIN ANALYZE

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT u.id, u.email, COUNT(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.created_at > NOW() - INTERVAL '30 days'
GROUP BY u.id, u.email
ORDER BY order_count DESC;
```

**Node types to watch:**

| Node | Signal | Fix |
|---|---|---|
| `Seq Scan` on large table | Missing or unused index | Add index on the filtered column |
| `Nested Loop` with large outer set | Potential N+1 pattern | Use `JOIN` or batch fetch; check for missing FK index |
| `Hash Join` | Generally efficient for large tables | Usually fine; watch for high memory usage |
| `Sort` without index | `ORDER BY` column not indexed | Add index on the sort column, or a composite covering index |
| `Bitmap Heap Scan` with high `rows removed` | Low selectivity index | Partial index or composite index with higher cardinality column first |

---

### N+1 Problem

```sql
-- BAD pattern (pseudocode): one query per user
SELECT * FROM users WHERE active = TRUE;
-- then for each user:
SELECT * FROM orders WHERE user_id = ?;
```

Fix in each ORM:

```python
# Python — SQLAlchemy: use selectinload for collections, joinedload for single relations
from sqlalchemy.orm import selectinload, joinedload

# Collection (one-to-many)
stmt = select(User).options(selectinload(User.orders)).where(User.active == True)

# Single relation (many-to-one)
stmt = select(Post).options(joinedload(Post.author))
```

```typescript
// TypeScript — Prisma: use include
const users = await prisma.user.findMany({
  where: { active: true },
  include: {
    orders: true,         // one-to-many
    profile: true,        // one-to-one
  },
});
```

```go
// Go — GORM: use Preload
var users []User
db.Where("active = ?", true).Preload("Orders").Find(&users)
```

---

### CTEs and Window Functions

```sql
-- CTE: use for readability; in PostgreSQL 12+ CTEs are inlined by default (no performance penalty)
WITH recent_orders AS (
    SELECT user_id, COUNT(*) AS order_count
    FROM orders
    WHERE created_at > NOW() - INTERVAL '90 days'
    GROUP BY user_id
)
SELECT u.email, ro.order_count
FROM users u
JOIN recent_orders ro ON ro.user_id = u.id
ORDER BY ro.order_count DESC;

-- Window function: prefer over correlated subqueries for running totals, ranks, lag/lead
SELECT
    id,
    user_id,
    amount,
    SUM(amount)   OVER (PARTITION BY user_id ORDER BY created_at) AS running_total,
    RANK()        OVER (PARTITION BY user_id ORDER BY amount DESC) AS rank_by_amount,
    LAG(amount)   OVER (PARTITION BY user_id ORDER BY created_at) AS prev_amount
FROM orders;
```

---

## Zero-Downtime Migrations

### Column Changes

**Adding a nullable column** — always safe, deploy any time.

```sql
-- Safe: nullable column can be added without locking
ALTER TABLE users ADD COLUMN middle_name TEXT;
```

**Adding a NOT NULL column** — never do this directly on a live table.

```sql
-- BAD: locks the table, breaks in-flight inserts that don't supply the column
ALTER TABLE users ADD COLUMN tier TEXT NOT NULL DEFAULT 'free';
```

Use the **expand-contract** pattern instead:

```sql
-- Step 1: add as nullable (no lock)
ALTER TABLE users ADD COLUMN tier TEXT;

-- Step 2: deploy app code that writes to both old and new column
-- (application handles NULL during backfill window)

-- Step 3: backfill existing rows in batches
UPDATE users SET tier = 'free' WHERE tier IS NULL AND id BETWEEN 1 AND 10000;
-- repeat for all id ranges...

-- Step 4: add NOT NULL + default (fast metadata-only change in PG 11+)
ALTER TABLE users ALTER COLUMN tier SET DEFAULT 'free';
ALTER TABLE users ALTER COLUMN tier SET NOT NULL;

-- Step 5 (later deployment): clean up any old column if you renamed
```

**Renaming a column** — use the same expand-contract pattern; never rename directly.

```sql
-- BAD: any code still using old column name breaks immediately
ALTER TABLE users RENAME COLUMN full_name TO display_name;

-- GOOD: add new column, dual-write, backfill, cut over, drop old column
ALTER TABLE users ADD COLUMN display_name TEXT;
-- (deploy code writing to both full_name and display_name)
UPDATE users SET display_name = full_name WHERE display_name IS NULL;
-- (deploy code reading from display_name only)
ALTER TABLE users DROP COLUMN full_name;
```

---

### Index Creation

```sql
-- BAD: blocks all writes on a busy production table until index is built
CREATE INDEX idx_orders_user_id ON orders (user_id);

-- GOOD: builds concurrently — takes longer but does not block inserts/updates/deletes
CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders (user_id);
```

`CREATE INDEX CONCURRENTLY` requires two table scans and cannot run inside a transaction block, but it is the only safe option on a live table with active write traffic.

---

### Migration Tools

| Language | Tool | Config File | Run Command |
|---|---|---|---|
| Python | Alembic | `alembic.ini` | `alembic upgrade head` |
| TypeScript | Prisma Migrate | `schema.prisma` | `prisma migrate deploy` |
| Go | golang-migrate | directory of `.sql` files | `migrate -path ./migrations -database $DB_URL up` |

```python
# Python — Alembic: auto-generate a migration from model changes
# alembic revision --autogenerate -m "add tier column to users"

def upgrade() -> None:
    op.add_column("users", sa.Column("tier", sa.Text(), nullable=True))
    op.execute("UPDATE users SET tier = 'free' WHERE tier IS NULL")
    op.alter_column("users", "tier", nullable=False, server_default="free")

def downgrade() -> None:
    op.drop_column("users", "tier")
```

```typescript
// TypeScript — Prisma schema change triggers a migration file on `prisma migrate dev`
// schema.prisma
model User {
  id          Int      @id @default(autoincrement())
  email       String   @unique
  tier        String   @default("free")
  createdAt   DateTime @default(now()) @map("created_at")

  @@map("users")
}
```

```go
// Go — golang-migrate: migration files are plain SQL
// migrations/000003_add_tier_to_users.up.sql
// ALTER TABLE users ADD COLUMN tier TEXT;
// UPDATE users SET tier = 'free' WHERE tier IS NULL;
// ALTER TABLE users ALTER COLUMN tier SET NOT NULL;
// ALTER TABLE users ALTER COLUMN tier SET DEFAULT 'free';

// migrations/000003_add_tier_to_users.down.sql
// ALTER TABLE users DROP COLUMN tier;

// Run in code:
import "github.com/golang-migrate/migrate/v4"

m, err := migrate.New("file://migrations", os.Getenv("DATABASE_URL"))
if err != nil {
    log.Fatal(err)
}
if err := m.Up(); err != nil && err != migrate.ErrNoChange {
    log.Fatal(err)
}
```

---

## Connection Management

### Pool Sizing

**Rule of thumb (PgBouncer):**

```
pool_size = (num_cores × 2) + effective_spindle_count
```

For a 4-core machine with SSD (spindle count = 1): `pool_size = (4 × 2) + 1 = 9`. Round up to 10.

- Practical starting point: 10–20 connections per app instance; monitor `pg_stat_activity` and tune.
- PostgreSQL has a hard limit (`max_connections`, default 100). Each connection uses ~5–10 MB of memory.
- When running more than a handful of app instances, place **PgBouncer** in front of PostgreSQL in transaction-pooling mode to multiplex hundreds of app connections onto a small pool.

---

### ORM Pool Configuration

```python
# Python — SQLAlchemy
from sqlalchemy import create_engine

engine = create_engine(
    os.environ["DATABASE_URL"],
    pool_size=10,       # number of persistent connections
    max_overflow=20,    # extra connections allowed under burst load
    pool_timeout=30,    # seconds to wait for a connection before raising
    pool_pre_ping=True, # test connection health before use
)
```

```typescript
// TypeScript — Prisma (via DATABASE_URL query params)
// DATABASE_URL="postgresql://user:pass@host:5432/db?connection_limit=10&pool_timeout=20"

// prisma/schema.prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

```go
// Go — pgx pool
import (
    "context"
    "github.com/jackc/pgx/v5/pgxpool"
)

config, err := pgxpool.ParseConfig(os.Getenv("DATABASE_URL"))
if err != nil {
    log.Fatal(err)
}
config.MaxConns = 20
config.MinConns = 2

pool, err := pgxpool.NewWithConfig(context.Background(), config)
if err != nil {
    log.Fatal(err)
}
defer pool.Close()
```

---

### Timeouts

Set timeouts to prevent runaway queries from blocking the pool and degrading the entire service.

```sql
-- Statement timeout: kill a query that runs longer than 30 seconds
SET statement_timeout = '30s';

-- Lock timeout: fail immediately rather than waiting indefinitely for a lock
SET lock_timeout = '5s';

-- Idle-in-transaction timeout: reclaim connections left open in a transaction
SET idle_in_transaction_session_timeout = '60s';
```

Configure at the role level so all connections inherit the setting:

```sql
ALTER ROLE app_user SET statement_timeout = '30s';
ALTER ROLE app_user SET lock_timeout = '5s';
ALTER ROLE app_user SET idle_in_transaction_session_timeout = '60s';
```

Or apply per-session in application code at connection acquisition time.

---

## Checklist

- [ ] Schema is at least 3NF; any denormalization is documented with rationale
- [ ] Primary keys use `BIGSERIAL` or UUID v7 (not UUID v4 unless interoperating with a distributed system that requires it)
- [ ] All timestamps use `TIMESTAMPTZ`, not `TIMESTAMP`
- [ ] Money and financial values stored as `NUMERIC`, not `FLOAT`
- [ ] Foreign keys have explicit `ON DELETE` behavior defined (not left as default `NO ACTION` silently)
- [ ] Indexes added for all foreign key columns and frequent `WHERE` / `ORDER BY` predicates
- [ ] Composite index column order: equality columns first, range columns last
- [ ] No `CREATE INDEX` without `CONCURRENTLY` on a live table with active traffic
- [ ] New `NOT NULL` columns added via expand-contract pattern, not direct `ALTER TABLE ... NOT NULL`
- [ ] `EXPLAIN (ANALYZE, BUFFERS)` run on all queries touching tables with more than 100k rows
- [ ] Connection pool sized appropriately; PgBouncer in place if running more than a handful of app instances
- [ ] Migration tool in use; all migrations are version-controlled and include a `downgrade` / `.down.sql` path
