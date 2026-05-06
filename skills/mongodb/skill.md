---
name: mongodb
description: Use when writing async MongoDB queries with Motor, designing aggregation pipelines, creating indexes, running multi-document transactions, or working with adk.state in Agentex agents.
---

# MongoDB — Async Patterns with Motor

Async MongoDB via Motor, aggregation pipelines, and index design.

## When to Activate

- Writing async MongoDB queries with Motor
- Designing aggregation pipelines (`$match`, `$group`, `$lookup`, `$unwind`)
- Creating indexes (compound, text, TTL, sparse, partial)
- Running multi-document transactions
- Watching for real-time changes with change streams
- Working with `adk.state` (Agentex per-task state backed by MongoDB)
- Designing document schemas for flexible or hierarchical data

---

## Connection

```python
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

client = AsyncIOMotorClient("mongodb://localhost:27017")
db: AsyncIOMotorDatabase = client["mydb"]

# With auth + replica set (production)
client = AsyncIOMotorClient(
    "mongodb://user:pass@host1:27017,host2:27017/mydb?replicaSet=rs0&authSource=admin"
)

# Close on shutdown
client.close()
```

Collections are accessed as attributes — no schema declaration needed:
```python
users = db["users"]              # or db.users
orders = db.orders
```

---

## CRUD

```python
from datetime import datetime, timezone
from bson import ObjectId

# Insert one
result = await db.users.insert_one({
    "email": "alice@example.com",
    "name": "Alice",
    "role": "user",
    "created_at": datetime.now(timezone.utc),
})
inserted_id = result.inserted_id   # ObjectId

# Insert many
result = await db.users.insert_many([
    {"email": "bob@example.com", "name": "Bob"},
    {"email": "carol@example.com", "name": "Carol"},
])

# Find one
user = await db.users.find_one({"email": "alice@example.com"})
user = await db.users.find_one({"_id": ObjectId("64a...")})

# Find many — returns an async cursor
cursor = db.users.find({"role": "admin"}).sort("created_at", -1).skip(0).limit(20)
users = await cursor.to_list(length=None)   # length=None = all results

# Count
count = await db.users.count_documents({"role": "admin"})
estimated = await db.users.estimated_document_count()   # fast, uses metadata

# Update one
result = await db.users.update_one(
    {"_id": ObjectId("64a...")},
    {"$set": {"role": "admin", "updated_at": datetime.now(timezone.utc)}},
)
matched = result.matched_count
modified = result.modified_count

# Update many
await db.users.update_many(
    {"role": "user", "created_at": {"$lt": cutoff_date}},
    {"$set": {"tier": "legacy"}},
)

# Upsert
await db.users.update_one(
    {"email": "dave@example.com"},
    {"$setOnInsert": {"created_at": datetime.now(timezone.utc)},
     "$set": {"name": "Dave", "role": "user"}},
    upsert=True,
)

# Delete
await db.users.delete_one({"_id": ObjectId("64a...")})
await db.users.delete_many({"status": "inactive", "created_at": {"$lt": cutoff}})

# Find one and update (atomic — returns updated doc)
updated = await db.users.find_one_and_update(
    {"_id": ObjectId("64a...")},
    {"$inc": {"login_count": 1}},
    return_document=True,    # return doc after update
)
```

---

## Query Operators

```python
# Comparison
{"age": {"$gt": 18, "$lte": 65}}
{"status": {"$in": ["active", "pending"]}}
{"status": {"$nin": ["banned", "deleted"]}}
{"score": {"$ne": 0}}

# Logical
{"$and": [{"role": "admin"}, {"active": True}]}
{"$or":  [{"email": {"$regex": "@company.com"}}, {"role": "admin"}]}
{"$not": {"status": "banned"}}

# Array operators
{"tags": {"$all": ["python", "async"]}}        # array contains all
{"tags": {"$elemMatch": {"$gt": 10, "$lt": 20}}}  # element matching condition
{"tags.2": "python"}                           # index access

# Element operators
{"phone": {"$exists": True}}
{"age":   {"$type": "int"}}

# Regex
{"email": {"$regex": "^admin", "$options": "i"}}

# Nested document
{"address.city": "New York"}
{"address.zip": {"$in": ["10001", "10002"]}}
```

---

## Update Operators

```python
# $set — update or add fields
{"$set": {"name": "Alice", "role": "admin"}}

# $unset — remove fields
{"$unset": {"temp_token": "", "legacy_field": ""}}

# $inc — atomic increment
{"$inc": {"login_count": 1, "score": -5}}

# $push — append to array
{"$push": {"tags": "python"}}
{"$push": {"events": {"$each": ["a", "b"], "$slice": -100}}}  # keep last 100

# $addToSet — append only if not present (unique set)
{"$addToSet": {"permissions": "write"}}

# $pull — remove from array
{"$pull": {"tags": "deprecated"}}
{"$pull": {"events": {"type": "click"}}}   # remove matching sub-docs

# $setOnInsert — only set on upsert insert (not on update)
{"$setOnInsert": {"created_at": datetime.now(timezone.utc)}}
```

---

## Aggregation Pipeline

```python
# Basic aggregation — group orders by status with total revenue
pipeline = [
    {"$match": {"created_at": {"$gte": start_date}}},
    {"$group": {
        "_id": "$status",
        "count": {"$sum": 1},
        "total_revenue": {"$sum": "$total"},
        "avg_order": {"$avg": "$total"},
    }},
    {"$sort": {"total_revenue": -1}},
]
results = await db.orders.aggregate(pipeline).to_list(None)

# $lookup — JOIN equivalent
pipeline = [
    {"$match": {"role": "admin"}},
    {"$lookup": {
        "from": "orders",           # collection to join
        "localField": "_id",        # field from users
        "foreignField": "user_id",  # field from orders
        "as": "orders",             # output array field
    }},
    {"$addFields": {"order_count": {"$size": "$orders"}}},
    {"$project": {"name": 1, "email": 1, "order_count": 1, "_id": 0}},
]

# $unwind — flatten array field into separate documents
pipeline = [
    {"$unwind": "$items"},          # one doc per item
    {"$group": {
        "_id": "$items.product_id",
        "total_sold": {"$sum": "$items.quantity"},
    }},
]

# $facet — multiple aggregations in one query
pipeline = [
    {"$match": {"status": "active"}},
    {"$facet": {
        "by_role": [
            {"$group": {"_id": "$role", "count": {"$sum": 1}}},
        ],
        "total": [
            {"$count": "count"},
        ],
        "recent": [
            {"$sort": {"created_at": -1}},
            {"$limit": 5},
            {"$project": {"name": 1, "email": 1}},
        ],
    }},
]

# $bucket — range bucketing
pipeline = [
    {"$bucket": {
        "groupBy": "$total",
        "boundaries": [0, 50, 100, 500, 1000],
        "default": "1000+",
        "output": {"count": {"$sum": 1}, "avg": {"$avg": "$total"}},
    }},
]
```

---

## Indexes

```python
# Ensure indexes at startup (idempotent — no-op if already exists)
async def create_indexes(db):
    # Single field
    await db.users.create_index("email", unique=True)

    # Compound — order matters (equality first, range last, sort last)
    await db.orders.create_index([("user_id", 1), ("status", 1), ("created_at", -1)])

    # Text search index
    await db.articles.create_index([("title", "text"), ("body", "text")])

    # TTL — auto-delete documents after expiry_at
    await db.sessions.create_index("expires_at", expireAfterSeconds=0)

    # Sparse — only index docs where field exists
    await db.users.create_index("stripe_customer_id", sparse=True, unique=True)

    # Partial — only index matching docs (smaller index)
    await db.orders.create_index(
        "created_at",
        partialFilterExpression={"status": "active"},
    )
```

In Agentex, indexes are defined in `src/config/mongodb_indexes.py` and created on startup automatically.

---

## Transactions (multi-document)

```python
# Requires replica set (or mongos)
async with await client.start_session() as session:
    async with session.start_transaction():
        await db.accounts.update_one(
            {"_id": from_id},
            {"$inc": {"balance": -amount}},
            session=session,
        )
        await db.accounts.update_one(
            {"_id": to_id},
            {"$inc": {"balance": amount}},
            session=session,
        )
        # auto-commits if no exception, auto-aborts on exception
```

---

## Change Streams (real-time)

```python
# Watch a collection for changes
async def watch_orders():
    pipeline = [{"$match": {"operationType": {"$in": ["insert", "update"]}}}]
    async with db.orders.watch(pipeline) as stream:
        async for change in stream:
            op = change["operationType"]       # "insert", "update", "delete"
            doc = change.get("fullDocument")   # updated document (for insert/update)
            keys = change.get("updateDescription", {}).get("updatedFields", {})
            yield op, doc, keys
```

Requires replica set. Use change streams to push updates to SSE clients without polling.

---

## Agentex `adk.state` Pattern

`adk.state` is MongoDB-backed per-task state storage. Under the hood it's a document per `(task_id, agent_id)`.

```python
from agentex.lib import adk
from project.models import SummarizerState

# Create initial state (insert)
await adk.state.create(
    task_id=task_id,
    agent_id=agent_id,
    data=SummarizerState().model_dump(),
)

# Load state (find_one by task_id + agent_id)
raw = await adk.state.get_by_task_and_agent(task_id=task_id, agent_id=agent_id)
state = SummarizerState(**raw.data)

# Mutate and save (update_one with $set)
state.total_processed += len(batch)
await adk.state.update(
    task_id=task_id,
    agent_id=agent_id,
    data=state.model_dump(),
)
```

Always load → mutate → save in sequence. Never hold state in workflow memory — Temporal replays will lose it.

---

## Document Design Tips

| Pattern | When | Example |
|---|---|---|
| Embed sub-documents | Read together always | `order.items[]` inside order doc |
| Reference (store ID) | Independent lifecycle, large sub-docs | `order.user_id` → users collection |
| Bucket pattern | Time-series data, many small writes | One doc per hour with `readings[]` array |
| Computed fields | Expensive aggregations read often | Store `order_count` on user doc, update with `$inc` |
| Schema versioning | Evolving document shape | Add `schema_version` field, migrate lazily |

---

## Red Flags

- **No index on query filter or sort fields** — MongoDB performs a collection scan for every unindexed query; `find({"user_id": x})` on a million-document collection takes seconds without an index on `user_id`
- **Unbounded `find()` in production** — `db.collection.find({})` without `.limit()` loads the entire collection into memory; always add `.limit(N)` and paginate with a cursor
- **`$match` not as the first pipeline stage** — aggregation stages before `$match` process every document before filtering; placing `$match` first lets MongoDB use indexes and dramatically reduces the work for subsequent stages
- **`datetime.utcnow()` instead of `datetime.now(timezone.utc)`** — `utcnow()` returns a naive datetime with no timezone info and is deprecated in Python 3.12; use `datetime.now(timezone.utc)` to get a timezone-aware UTC datetime that Motor stores correctly
- **Transactions without a replica set** — `client.start_session()` multi-document transactions require a replica set (or `mongos`); on a standalone instance they raise a server error; use a replica set even in development (`mongo --replSet rs0`)
- **Embedding unbounded arrays** — pushing to a `tags[]` or `events[]` array without a `$slice` limit grows the document indefinitely, eventually hitting the 16 MB BSON document size limit; cap arrays at creation time using `$push` with `$slice`
- **Holding state in workflow memory instead of `adk.state`** — Temporal replays recreate the workflow from scratch; any in-memory state not persisted to MongoDB via `adk.state` is lost on replay, causing the workflow to behave differently than the first execution

## Checklist

- [ ] Indexes created at startup for all query filter and sort fields
- [ ] Compound indexes: equality fields first, range/sort fields last
- [ ] TTL index used for session/temp data instead of manual cleanup
- [ ] `find()` always has `.limit()` — never unbounded cursor in production
- [ ] Aggregation `$match` is the first stage (filters before loading docs)
- [ ] `$lookup` result arrays have `$limit` or `$slice` if sub-docs can be large
- [ ] Transactions used for multi-collection writes that must be atomic
- [ ] `adk.state` always follows load → mutate → save pattern in Temporal activities
- [ ] `datetime.now(timezone.utc)` used (not `datetime.utcnow()` — deprecated)
