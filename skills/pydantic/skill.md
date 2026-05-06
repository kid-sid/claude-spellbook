---
name: pydantic
description: Use when defining request/response schemas, writing custom validators, controlling serialization for PATCH endpoints, validating non-model data with TypeAdapter, or configuring app settings from environment variables with pydantic-settings.
---

# Pydantic v2 Patterns

Validation, serialization, and settings management with Pydantic v2.

## When to Activate

- Defining request/response schemas or domain models
- Writing `@field_validator` or `@model_validator` for custom validation
- Using `Annotated` to build reusable constrained types
- Controlling serialization with `model_dump()` / `model_dump_json()`
- Building generic models or discriminated unions
- Validating arbitrary data (not a model) with `TypeAdapter`
- Configuring app settings from environment variables with `pydantic-settings`

---

## BaseModel Basics

```python
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

class User(BaseModel):
    id: UUID
    name: str
    email: str
    age: int = Field(ge=0, le=150)
    role: str = "user"          # default value
    created_at: datetime | None = None

# Instantiate
user = User(id="a1b2...", name="Alice", email="alice@example.com", age=30)

# Access
user.name        # "Alice"
user.model_fields  # dict of FieldInfo

# Validate from dict / JSON
user = User.model_validate({"id": "...", "name": "Alice", ...})
user = User.model_validate_json('{"id": "...", "name": "Alice", ...}')
```

---

## Field Constraints

```python
from pydantic import BaseModel, Field
from typing import Annotated

class Product(BaseModel):
    name: str = Field(min_length=1, max_length=200, strip_whitespace=True)
    price: float = Field(gt=0, description="Price in USD")
    discount: float = Field(ge=0, le=1, default=0.0)    # 0–100%
    tags: list[str] = Field(default_factory=list, max_length=10)
    sku: str = Field(pattern=r"^[A-Z]{3}-\d{6}$")
    metadata: dict = Field(default_factory=dict)

    # Alias — accept "product_name" in input, use "name" in Python
    name: str = Field(alias="product_name")
```

### Reusable constrained types with `Annotated`

```python
from typing import Annotated
from pydantic import Field

# Define once, reuse everywhere
PositiveInt   = Annotated[int,   Field(gt=0)]
Percentage    = Annotated[float, Field(ge=0.0, le=1.0)]
NonEmptyStr   = Annotated[str,   Field(min_length=1, strip_whitespace=True)]
EmailStr      = Annotated[str,   Field(pattern=r"^[^@]+@[^@]+\.[^@]+$")]
UserId        = Annotated[str,   Field(min_length=36, max_length=36)]

class CreateUserRequest(BaseModel):
    name: NonEmptyStr
    email: EmailStr
    age: PositiveInt
    discount: Percentage = 0.0
```

---

## Validators

### `@field_validator` — validate / transform a single field

```python
from pydantic import BaseModel, field_validator

class User(BaseModel):
    name: str
    email: str
    role: str

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        allowed = {"admin", "user", "viewer"}
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed}")
        return v

    # Validate multiple fields at once
    @field_validator("name", "email", mode="before")  # runs before type coercion
    @classmethod
    def strip_strings(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v
```

`mode="before"` runs before type coercion. `mode="after"` (default) runs after.

### `@model_validator` — validate across multiple fields

```python
from pydantic import BaseModel, model_validator

class DateRange(BaseModel):
    start_date: datetime
    end_date: datetime
    max_days: int = 90

    @model_validator(mode="after")
    def check_date_range(self) -> "DateRange":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        delta = (self.end_date - self.start_date).days
        if delta > self.max_days:
            raise ValueError(f"Range cannot exceed {self.max_days} days")
        return self

class PasswordReset(BaseModel):
    password: str
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordReset":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

# mode="before" — receives raw dict, before field validation
    @model_validator(mode="before")
    @classmethod
    def handle_legacy_format(cls, data: dict) -> dict:
        if "user_name" in data:
            data["name"] = data.pop("user_name")   # rename legacy field
        return data
```

---

## ConfigDict

```python
from pydantic import BaseModel, ConfigDict

class UserResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,       # allow ORM model → Pydantic (was orm_mode in v1)
        populate_by_name=True,      # accept both alias and field name
        str_strip_whitespace=True,  # strip whitespace from all str fields
        str_to_lower=False,
        extra="forbid",             # reject unknown fields (good for request schemas)
        # extra="ignore"            # silently drop unknown fields
        # extra="allow"             # keep unknown fields in __pydantic_extra__
        frozen=True,                # immutable instances (hashable)
        arbitrary_types_allowed=True,  # allow non-Pydantic types
        json_schema_extra={"example": {"name": "Alice", "email": "alice@example.com"}},
    )
```

---

## Serialization

```python
user = User(id=uuid4(), name="Alice", email="alice@example.com", role="admin")

# To dict
user.model_dump()
user.model_dump(exclude={"password", "internal_id"})
user.model_dump(include={"id", "name", "email"})
user.model_dump(exclude_none=True)      # omit None values
user.model_dump(exclude_unset=True)     # omit fields not explicitly set (useful for PATCH)
user.model_dump(by_alias=True)          # use field aliases as keys
user.model_dump(mode="json")            # serialize to JSON-compatible types (UUID → str)

# To JSON string
user.model_dump_json()
user.model_dump_json(indent=2, exclude_none=True)

# From ORM (with from_attributes=True)
orm_user = db.query(UserORM).first()
user = UserResponse.model_validate(orm_user)

# Copy with overrides
updated = user.model_copy(update={"role": "admin"})
```

---

## Discriminated Unions

```python
from pydantic import BaseModel
from typing import Literal, Union, Annotated
from pydantic import Field

class CreditCard(BaseModel):
    type: Literal["credit_card"]
    number: str
    expiry: str
    cvv: str

class BankTransfer(BaseModel):
    type: Literal["bank_transfer"]
    account_number: str
    routing_number: str

class Crypto(BaseModel):
    type: Literal["crypto"]
    wallet_address: str
    currency: str

PaymentMethod = Annotated[
    Union[CreditCard, BankTransfer, Crypto],
    Field(discriminator="type"),   # Pydantic uses "type" to pick the right model
]

class Order(BaseModel):
    id: str
    payment: PaymentMethod

# Pydantic automatically picks the right union member
order = Order.model_validate({
    "id": "o-123",
    "payment": {"type": "credit_card", "number": "4111...", "expiry": "12/26", "cvv": "123"},
})
isinstance(order.payment, CreditCard)  # True
```

---

## Generic Models

```python
from pydantic import BaseModel
from typing import TypeVar, Generic

T = TypeVar("T")

class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool

class ApiResponse(BaseModel, Generic[T]):
    data: T
    status: int = 200
    message: str = "ok"

# Concrete usage — fully typed
users_page: Page[User] = Page[User](items=[...], total=100, page=1, page_size=20, has_next=True)
response: ApiResponse[User] = ApiResponse[User](data=user)
```

---

## TypeAdapter — validate without a model

```python
from pydantic import TypeAdapter

# Validate a plain type or complex type
ta = TypeAdapter(list[int])
ta.validate_python([1, 2, "3"])   # [1, 2, 3] — coerces "3" to 3
ta.validate_json("[1, 2, 3]")

# Validate arbitrary dict shape
ta = TypeAdapter(dict[str, list[int]])
ta.validate_python({"a": [1, 2], "b": [3]})

# Great for validating webhook payloads, external API responses
StrippedStr = Annotated[str, Field(strip_whitespace=True, min_length=1)]
ta = TypeAdapter(StrippedStr)
ta.validate_python("  hello  ")   # "hello"
```

---

## pydantic-settings

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Required — raises if missing from env
    database_url: str
    secret_key: str

    # Optional with defaults
    environment: str = "development"
    debug: bool = False
    redis_url: str = "redis://localhost:6379"
    allowed_origins: list[str] = ["http://localhost:3000"]

    # Nested prefix: reads TEMPORAL__ADDRESS from env
    temporal_address: str = Field("localhost:7233", alias="TEMPORAL_ADDRESS")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()   # cached singleton
```

Env var names match field names case-insensitively. `list[str]` reads from `ALLOWED_ORIGINS=http://a.com,http://b.com` (comma-separated).

---

## Red Flags

- **Sharing API schemas with the domain layer** — using the same Pydantic model as both the HTTP request schema and the internal domain entity couples the API contract to business logic; changes to the API surface silently affect domain behavior and vice versa
- **Mutable field defaults without `default_factory`** — `tags: list[str] = []` shares the same list object across all instances; use `tags: list[str] = Field(default_factory=list)` for any mutable default
- **Not using `model_dump(exclude_unset=True)` for PATCH** — `model_dump()` on a partial-update model includes all fields set to their defaults, overwriting database values the client never sent; `exclude_unset=True` returns only the fields the caller explicitly provided
- **`orm_mode = True` (v1 syntax) in a v2 project** — the v1 config key is silently ignored in Pydantic v2; use `model_config = ConfigDict(from_attributes=True)` instead
- **Catching bare `Exception` from `model_validate`** — validation errors from Pydantic are `ValidationError`, not `ValueError` or `Exception`; catching the wrong type means bad input crashes the caller with an unhandled exception instead of a structured error response
- **`model_dump()` when JSON-safe types are needed** — `model_dump()` returns Python objects (UUID, datetime, Decimal) that are not JSON-serializable; use `model_dump(mode="json")` or `model_dump_json()` when the result will be serialized to JSON or stored as a dict in MongoDB
- **Repeating `Field(gt=0)` on every model instead of `Annotated` types** — duplicating constraints is error-prone and hard to update; define `PositiveInt = Annotated[int, Field(gt=0)]` once and reuse it everywhere

## Checklist

- [ ] `Annotated` used to define reusable constrained types (not repeating Field() everywhere)
- [ ] `@field_validator` with `mode="before"` for input normalization (strip, lowercase)
- [ ] `@model_validator` for cross-field validation (date ranges, password confirm)
- [ ] `from_attributes=True` in `ConfigDict` for ORM → schema conversion
- [ ] `extra="forbid"` on request schemas to reject unknown input
- [ ] `model_dump(exclude_unset=True)` for PATCH endpoints (only update what was sent)
- [ ] `model_dump(mode="json")` when serializing UUIDs/datetimes to dicts
- [ ] `TypeAdapter` for validating non-model types (lists, dicts, scalars)
- [ ] `pydantic-settings` for all environment variable config (not raw `os.environ`)
- [ ] `@lru_cache` on `get_settings()` — load once, reuse
