---
name: graphql
description: Use when designing a GraphQL schema, implementing resolvers or mutations, solving the N+1 query problem with DataLoader, setting up subscriptions, paginating with Cursor Connections, securing a GraphQL API, or choosing between GraphQL and REST.
---

# GraphQL

Schema design, resolver patterns, performance, and security for production GraphQL APIs.

## When to Activate

- Designing types, queries, mutations, or subscriptions in a GraphQL schema
- Implementing resolvers in Python (Strawberry/Ariadne), TypeScript (Apollo/Pothos), or Go (gqlgen)
- Solving N+1 query problems with DataLoader
- Paginating results with Cursor Connections
- Securing a GraphQL endpoint against introspection, depth attacks, or query abuse
- Choosing between GraphQL and REST for a new API
- Setting up real-time updates with subscriptions

---

## GraphQL vs. REST

| Concern | GraphQL | REST |
|---|---|---|
| Data fetching | Client specifies exact fields | Server defines response shape |
| Multiple resources | Single request | One request per resource |
| Versioning | Schema evolves via deprecation | URL or header versioning |
| Caching | Complex (query-level) | Simple (HTTP cache headers) |
| File uploads | Non-standard | Native multipart |
| Best for | Flexible client needs, multiple consumers | Simple CRUD, public APIs, CDN caching |

Use GraphQL when you have multiple clients (web, mobile, third-party) with different data needs. Prefer REST for simple CRUD with aggressive HTTP caching.

---

## Schema Design

### Type Conventions

```graphql
# Scalar types
scalar DateTime   # ISO-8601 string
scalar UUID
scalar JSON

# Object type — PascalCase, fields camelCase
type User {
  id: ID!
  email: String!
  createdAt: DateTime!
  orders(first: Int, after: String): OrderConnection!
}

# Input type — suffix with Input
input CreateUserInput {
  email: String!
  name: String!
}

# Enum — SCREAMING_SNAKE_CASE values
enum OrderStatus {
  PENDING
  PROCESSING
  COMPLETED
  CANCELLED
}

# Interface — shared fields across types
interface Node {
  id: ID!
}

# Union — one of several types
union SearchResult = User | Product | Order
```

### Nullable vs. Non-Null

| Pattern | Schema | When to use |
|---|---|---|
| Always present | `field: String!` | Required data — fetch fails if missing |
| Optional | `field: String` | May legitimately be absent |
| List always present | `items: [Item!]!` | List itself and items always exist |
| List may be absent | `items: [Item!]` | Null means "not loaded", `[]` means "empty" |

**Prefer non-null (`!`) for fields that are always present.** Nullable fields force every client to null-check; use them only when absence is meaningful.

### Mutations

```graphql
# BAD — returns the raw type
type Mutation {
  createUser(email: String!, name: String!): User
}

# GOOD — dedicated payload type with errors
type Mutation {
  createUser(input: CreateUserInput!): CreateUserPayload!
  updateUser(id: ID!, input: UpdateUserInput!): UpdateUserPayload!
  deleteUser(id: ID!): DeleteUserPayload!
}

type CreateUserPayload {
  user: User          # null on failure
  errors: [UserError!]!
}

type UserError {
  field: String       # null for non-field errors
  message: String!
  code: String!
}
```

Mutation payload types give clients a typed error path without relying on the `errors` top-level array.

---

## Cursor Connections (Pagination)

Use the Relay Cursor Connection spec for all list fields — it handles forward, backward, and arbitrary pagination consistently.

```graphql
type UserConnection {
  edges: [UserEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type UserEdge {
  node: User!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}

type Query {
  users(first: Int, after: String, last: Int, before: String): UserConnection!
}
```

```python
# Python — cursor is base64(type:id)
import base64

def encode_cursor(type_name: str, id: str) -> str:
    return base64.b64encode(f"{type_name}:{id}".encode()).decode()

def decode_cursor(cursor: str) -> tuple[str, str]:
    decoded = base64.b64decode(cursor.encode()).decode()
    type_name, id = decoded.split(":", 1)
    return type_name, id
```

---

## Resolvers and the N+1 Problem

### The Problem

```
Query: { users { id orders { id total } } }

Naive resolver:
  SELECT * FROM users                    — 1 query
  SELECT * FROM orders WHERE user_id=1   — 1 query per user
  SELECT * FROM orders WHERE user_id=2
  SELECT * FROM orders WHERE user_id=3   — N queries for N users = N+1 total
```

### DataLoader (Batch + Cache)

```typescript
// TypeScript — Apollo Server with DataLoader
import DataLoader from "dataloader";

// One loader per request — never share across requests
function createLoaders() {
  return {
    ordersByUserId: new DataLoader<string, Order[]>(async (userIds) => {
      const orders = await db.order.findMany({
        where: { userId: { in: [...userIds] } },
      });
      // Return results in the same order as keys
      return userIds.map((id) => orders.filter((o) => o.userId === id));
    }),
  };
}

// Resolver
const resolvers = {
  User: {
    orders: (user, _args, { loaders }) =>
      loaders.ordersByUserId.load(user.id), // batched automatically
  },
};
```

```python
# Python — Strawberry with strawberry-django DataLoader
from strawberry.dataloader import DataLoader

async def load_orders(user_ids: list[str]) -> list[list[Order]]:
    orders = await Order.objects.filter(user_id__in=user_ids).all()
    mapping: dict[str, list[Order]] = {id: [] for id in user_ids}
    for order in orders:
        mapping[order.user_id].append(order)
    return [mapping[id] for id in user_ids]

orders_loader = DataLoader(load_fn=load_orders)
```

```go
// Go — gqlgen with graph-gophers/dataloader
loader := dataloader.NewBatchedLoader(func(ctx context.Context, keys dataloader.Keys) []*dataloader.Result {
    ids := make([]string, len(keys))
    for i, k := range keys { ids[i] = k.String() }

    orders, _ := db.FindOrdersByUserIDs(ctx, ids)

    // Map results back to key order
    results := make([]*dataloader.Result, len(keys))
    orderMap := groupByUserID(orders)
    for i, k := range keys {
        results[i] = &dataloader.Result{Data: orderMap[k.String()]}
    }
    return results
})
```

---

## Subscriptions

```graphql
type Subscription {
  orderStatusChanged(orderId: ID!): OrderStatusEvent!
}

type OrderStatusEvent {
  orderId: ID!
  status: OrderStatus!
  updatedAt: DateTime!
}
```

```typescript
// TypeScript — Apollo Server with Redis PubSub
import { RedisPubSub } from "graphql-redis-subscriptions";

const pubsub = new RedisPubSub({
  publisher: new Redis(process.env.REDIS_URL),
  subscriber: new Redis(process.env.REDIS_URL),
});

const resolvers = {
  Subscription: {
    orderStatusChanged: {
      subscribe: (_root, { orderId }) =>
        pubsub.asyncIterableIterator(`ORDER_STATUS:${orderId}`),
    },
  },
  Mutation: {
    updateOrderStatus: async (_root, { orderId, status }) => {
      const order = await db.order.update({ where: { id: orderId }, data: { status } });
      await pubsub.publish(`ORDER_STATUS:${orderId}`, { orderStatusChanged: order });
      return order;
    },
  },
};
```

---

## Security

### Query Complexity and Depth Limits

Without limits, a single query can exhaust server resources:

```graphql
# Depth attack
{ user { friends { friends { friends { friends { id } } } } } }

# Breadth attack — requests thousands of fields
{ users(first: 1000) { orders(first: 1000) { items(first: 1000) { id } } } }
```

```typescript
// TypeScript — graphql-depth-limit + graphql-query-complexity
import depthLimit from "graphql-depth-limit";
import { createComplexityLimitRule } from "graphql-query-complexity";

const server = new ApolloServer({
  validationRules: [
    depthLimit(5),
    createComplexityLimitRule(1000, {
      scalarCost: 1,
      objectCost: 2,
      listFactor: 10,
    }),
  ],
});
```

### Disable Introspection in Production

```typescript
const server = new ApolloServer({
  introspection: process.env.NODE_ENV !== "production",
});
```

### Field-Level Authorization

```python
# Python — Strawberry permission classes
import strawberry
from strawberry.permission import BasePermission

class IsAuthenticated(BasePermission):
    message = "Not authenticated"
    def has_permission(self, source, info, **kwargs) -> bool:
        return info.context.user is not None

class IsAdmin(BasePermission):
    message = "Admin access required"
    def has_permission(self, source, info, **kwargs) -> bool:
        return getattr(info.context.user, "role", None) == "admin"

@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAuthenticated])
    def me(self, info) -> User:
        return info.context.user

    @strawberry.field(permission_classes=[IsAdmin])
    def all_users(self, info) -> list[User]:
        return User.objects.all()
```

---

## Schema Evolution

| Change | Safe? | Notes |
|---|---|---|
| Add a field | Yes | Existing clients ignore unknown fields |
| Add a type | Yes | Not exposed until a query uses it |
| Add a non-null argument | No | Breaks clients not passing the argument |
| Add an optional argument | Yes | Default value required |
| Remove or rename a field | No | Deprecate first, remove after migration |
| Change field type | No | Always breaking |

```graphql
# Deprecate before removing — give clients time to migrate
type User {
  name: String @deprecated(reason: "Use `firstName` and `lastName` instead")
  firstName: String!
  lastName: String!
}
```

---

## Red Flags

- **Returning raw errors in the `errors` array for business failures** — use mutation payload types with a typed `errors` field; the top-level `errors` array is for server errors only.
- **No DataLoader for nested list resolvers** — every list field that loads related data without batching causes N+1 queries; instrument with query logging to catch them.
- **Introspection enabled in production** — exposes your full schema to attackers; disable it or restrict to authenticated users.
- **No depth or complexity limits** — a deeply nested query can exhaust CPU and memory; always set limits in validation rules.
- **Nullable everything** — excessive nullability forces clients to null-check every field; use `!` for fields that are always present.
- **Business logic in resolvers** — resolvers become untestable and duplicated; keep resolvers thin and delegate to a service layer.
- **Sharing DataLoader instances across requests** — DataLoaders cache per-request; a shared loader leaks data between users.
- **One mutation per field** — `updateUserName`, `updateUserEmail` as separate mutations is a smell; use `updateUser(input: UpdateUserInput!)` with partial input.

---

## Checklist

- [ ] All list fields use Cursor Connection pagination — no offset-based `skip`/`limit`
- [ ] Mutations return dedicated payload types with a typed `errors` field
- [ ] DataLoader used for every resolver that loads related entities — no N+1 queries
- [ ] Query depth limit set (max 5–7 levels)
- [ ] Query complexity limit set and tuned to realistic usage
- [ ] Introspection disabled in production
- [ ] Field-level authorization applied — not just route-level auth middleware
- [ ] Non-null (`!`) used for fields that are always present — nullable only where absence is meaningful
- [ ] Deprecated fields annotated with `@deprecated(reason: "...")` before removal
- [ ] DataLoader instances created per-request — never shared across requests
- [ ] Subscriptions use a pub/sub backend (Redis) — not in-memory for multi-instance deployments
- [ ] Schema linted with `graphql-inspector` or equivalent in CI
