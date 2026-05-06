---
name: sqlalchemy
description: Use when using async SQLAlchemy 2.0 — defining models, writing queries, managing async sessions, loading relationships without N+1, or setting up and debugging Alembic migrations.
---

# SQLAlchemy 2.0 — Async Patterns

Modern SQLAlchemy 2.0 with full async support (asyncpg) and Alembic migrations.

## When to Activate

- Defining ORM models with `Mapped` / `mapped_column`
- Writing async queries (`select`, `join`, `filter`, `order_by`)
- Managing async sessions (`AsyncSession`, `async_sessionmaker`)
- Handling relationships and loading strategies (`selectin`, `joined`, `lazy`)
- Running database transactions or bulk operations
- Writing or debugging Alembic migrations
- Converting between ORM models and domain entities

---

## Model Definition (SQLAlchemy 2.0 style)

```python
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, ForeignKey, Text, TIMESTAMP, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB


class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship — loads orders when accessed
    orders: Mapped[list["OrderORM"]] = relationship("OrderORM", back_populates="user")


class OrderORM(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    total: Mapped[float] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user: Mapped["UserORM"] = relationship("UserORM", back_populates="orders")
```

**Key rules:**
- `Mapped[T]` declares the Python type; `mapped_column()` declares the column config
- `nullable=False` is explicit — `Mapped[str]` without it is still nullable in older versions
- Use `PGUUID(as_uuid=True)` so SQLAlchemy returns Python `UUID` objects, not strings
- `index=True` on FK columns — always

---

## Engine and Session Factory

```python
# config/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# asyncpg driver — fastest PostgreSQL async driver
engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost:5432/mydb",
    pool_size=10,           # max persistent connections
    max_overflow=20,        # extra connections above pool_size under load
    pool_pre_ping=True,     # test connections before use (handles dropped connections)
    echo=False,             # set True to log all SQL (dev only)
)

# Session factory — reuse this, don't recreate per request
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,   # keep attributes accessible after commit
    autoflush=False,
)
```

---

## Dependency (FastAPI)

```python
# api/dependencies.py
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import AsyncSessionLocal

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

FastAPI caches this dependency within a request — one session per request.

---

## CRUD Patterns

```python
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

class UserCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: UUID) -> UserORM | None:
        result = await self.session.execute(
            select(UserORM).where(UserORM.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> UserORM | None:
        result = await self.session.execute(
            select(UserORM).where(UserORM.email == email)
        )
        return result.scalar_one_or_none()

    async def list(self, skip: int = 0, limit: int = 100) -> list[UserORM]:
        result = await self.session.execute(
            select(UserORM).order_by(UserORM.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, email: str, name: str, role: str = "user") -> UserORM:
        user = UserORM(email=email, name=name, role=role)
        self.session.add(user)
        await self.session.flush()   # assigns ID without committing
        await self.session.refresh(user)
        return user

    async def update(self, user_id: UUID, **kwargs) -> UserORM | None:
        await self.session.execute(
            update(UserORM).where(UserORM.id == user_id).values(**kwargs)
        )
        return await self.get(user_id)

    async def delete(self, user_id: UUID) -> None:
        await self.session.execute(
            delete(UserORM).where(UserORM.id == user_id)
        )

    async def count(self, role: str | None = None) -> int:
        from sqlalchemy import func
        q = select(func.count()).select_from(UserORM)
        if role:
            q = q.where(UserORM.role == role)
        result = await self.session.execute(q)
        return result.scalar_one()
```

---

## Joins and Complex Queries

```python
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload, joinedload

# JOIN — users with their order count
result = await session.execute(
    select(UserORM, func.count(OrderORM.id).label("order_count"))
    .outerjoin(OrderORM, UserORM.id == OrderORM.user_id)
    .group_by(UserORM.id)
    .order_by(func.count(OrderORM.id).desc())
)
rows = result.all()   # list of (UserORM, order_count) tuples

# Relationship loading — selectinload avoids N+1
result = await session.execute(
    select(UserORM)
    .options(selectinload(UserORM.orders))   # one extra query for all orders
    .where(UserORM.role == "admin")
)
users = result.scalars().all()
for user in users:
    print(user.orders)   # no extra query

# joinedload — single JOIN query (good for to-one relationships)
result = await session.execute(
    select(OrderORM)
    .options(joinedload(OrderORM.user))
    .where(OrderORM.status == "pending")
)
orders = result.unique().scalars().all()

# Filtering with operators
result = await session.execute(
    select(UserORM).where(
        and_(
            UserORM.role.in_(["admin", "manager"]),
            UserORM.created_at > datetime(2024, 1, 1),
            or_(
                UserORM.name.ilike("%alice%"),
                UserORM.email.ilike("%alice%"),
            ),
        )
    )
)

# JSONB filtering
result = await session.execute(
    select(UserORM).where(
        UserORM.metadata_["plan"].astext == "pro"
    )
)
```

---

## Loading Strategies

| Strategy | When to use | Extra queries |
|---|---|---|
| `selectinload` | One-to-many, loading multiple parents | 1 extra per relationship |
| `joinedload` | Many-to-one (loading parent from child) | 0 extra (JOIN) |
| `lazy="raise"` | Default in strict mode — force explicit loading | Raises if accessed |
| `lazy="noload"` | Never load — when you never need the relation | 0 |

```python
# Set default loading per model
class OrderORM(Base):
    user: Mapped["UserORM"] = relationship(
        "UserORM",
        back_populates="orders",
        lazy="raise",    # must explicitly use joinedload/selectinload in queries
    )
```

---

## Transactions

```python
# Session auto-handles transaction — commit/rollback in dependency

# Explicit savepoint (nested transaction)
async with session.begin_nested():
    session.add(obj)
    # rolls back to savepoint on exception, not the whole transaction

# Bulk insert (much faster than add() in a loop)
await session.execute(
    UserORM.__table__.insert(),
    [{"email": f"user{i}@test.com", "name": f"User {i}"} for i in range(1000)],
)

# Upsert (PostgreSQL ON CONFLICT)
from sqlalchemy.dialects.postgresql import insert

stmt = insert(UserORM).values(email="alice@example.com", name="Alice")
stmt = stmt.on_conflict_do_update(
    index_elements=["email"],
    set_={"name": stmt.excluded.name, "updated_at": func.now()},
)
await session.execute(stmt)
```

---

## Alembic Migrations

### Setup

```bash
# In agentex/:
alembic init alembic           # creates alembic/ dir + alembic.ini
# or with make:
make migration NAME="add_users_table"
make apply-migrations
```

`alembic/env.py` — connect to async engine and point at your models:

```python
from sqlalchemy.ext.asyncio import async_engine_from_config
from adapters.orm import Base    # import your Base so models are registered

target_metadata = Base.metadata

def run_migrations_online():
    connectable = async_engine_from_config(config.get_section(config.config_ini_section))
    # ... standard async alembic boilerplate
```

### Migration file patterns

```python
# Auto-generated migration — review before applying
def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

def downgrade() -> None:
    op.drop_table("users")

# Add column safely (large tables)
def upgrade() -> None:
    # Step 1: add nullable first (no table lock)
    op.add_column("orders", sa.Column("shipped_at", sa.TIMESTAMP(timezone=True), nullable=True))
    # Step 2: backfill (do in batches in a separate migration or via cron)
    # Step 3: add NOT NULL constraint after backfill

# Create index concurrently (no table lock)
def upgrade() -> None:
    op.execute("CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders(user_id)")

def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY idx_orders_user_id")

# Data migration
def upgrade() -> None:
    op.execute("UPDATE users SET role = 'member' WHERE role = 'user'")
```

---

## Entity Conversion

Keep ORM models separate from domain entities. Convert at the adapter boundary:

```python
# adapters/crud_store/users.py
from domain.entities.user import User
from adapters.orm import UserORM

def convert_user_to_entity(orm: UserORM) -> User:
    return User(
        id=orm.id,
        email=orm.email,
        name=orm.name,
        role=orm.role,
        created_at=orm.created_at,
    )

class UserRepository:
    async def get(self, user_id: UUID) -> User | None:
        orm = await UserCRUD(self.session).get(user_id)
        return convert_user_to_entity(orm) if orm else None
```

---

## Red Flags

- **Old-style `Column()` declarations** — `Column(String, nullable=False)` without `Mapped[T]` loses the Python type information that mypy and editors rely on; use `Mapped[str] = mapped_column(String(255), nullable=False)` in all new SQLAlchemy 2.0 code
- **Accessing relationships without explicit loading** — accessing `user.orders` in an async context without `selectinload` or `joinedload` raises `MissingGreenlet` or emits implicit lazy SQL that blocks the event loop; always declare the loading strategy in the query
- **Creating a new `AsyncSession` per query** — instantiating a session for each database call bypasses connection pooling and transaction batching; create one session per request via the FastAPI dependency
- **Missing `pool_pre_ping=True`** — without it, connections dropped by the database (idle timeout, network reset) are handed to the application as stale; the first query fails with a connection error rather than transparently reconnecting
- **`expire_on_commit=False` missing** — by default SQLAlchemy expires all attributes after commit; accessing them in an async context after the session commits triggers lazy loads that fail; set `expire_on_commit=False` in `async_sessionmaker`
- **Missing `index=True` on foreign key columns** — SQLAlchemy does not auto-index FK columns; every `JOIN` or filter on a FK without an index is a sequential scan
- **ORM models imported in the domain layer** — importing `UserORM` in use cases or domain entities couples the business logic to the database schema; all ORM ↔ entity conversion belongs in the adapter layer

## Checklist

- [ ] `Mapped[T]` + `mapped_column()` used (not old `Column()` style)
- [ ] FK columns have `index=True`
- [ ] `async_sessionmaker` with `expire_on_commit=False` for async
- [ ] `pool_pre_ping=True` on engine to handle dropped connections
- [ ] `selectinload` / `joinedload` explicit in every query that accesses a relationship
- [ ] `flush()` used after `add()` to get DB-generated ID without committing
- [ ] Alembic migrations add nullable columns first, then backfill, then add NOT NULL
- [ ] `CREATE INDEX CONCURRENTLY` used for large tables
- [ ] ORM models never imported in domain layer — conversion happens in adapter
