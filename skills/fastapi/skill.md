---
name: fastapi
description: Use when structuring a FastAPI application, designing dependency injection chains, defining Pydantic v2 schemas, adding JWT authentication, or writing async route tests with httpx.
---

# FastAPI Patterns

Modern FastAPI (0.100+) with Pydantic v2, async-first, and typed throughout.

## When to Activate

- Structuring a FastAPI app with routers and layered architecture
- Designing dependency injection chains with `Depends`
- Defining Pydantic v2 request/response schemas
- Handling errors, custom exception handlers, or middleware
- Adding authentication (OAuth2, JWT, API keys)
- Writing background tasks or startup/shutdown logic
- Testing FastAPI routes with `TestClient` or async `httpx`

---

## Project Structure

```
src/
├── api/
│   ├── app.py              # create_app(), register routers + middleware
│   ├── dependencies.py     # shared Depends (db session, current user, etc.)
│   ├── middleware.py        # CORS, logging, request ID
│   └── routes/
│       ├── users.py
│       └── orders.py
├── domain/
│   ├── entities/           # Pure Pydantic models — no ORM, no HTTP
│   ├── use_cases/          # Business logic — orchestrates services
│   └── repositories/       # Abstract interfaces (Protocol or ABC)
├── adapters/
│   ├── database/           # SQLAlchemy models + session factory
│   ├── crud/               # Concrete repository implementations
│   └── external/           # Third-party HTTP clients
├── config/
│   ├── settings.py         # Pydantic Settings (env vars)
│   └── dependencies.py     # App-wide singletons (DB engine, Redis, etc.)
└── main.py                 # uvicorn entry point
```

---

## App Factory

```python
# api/app.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.dependencies import GlobalDependencies
from api.routes import users, orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize singletons, DB pools, caches
    await GlobalDependencies.initialize()
    yield
    # Shutdown: close connections cleanly
    await GlobalDependencies.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="My API",
        version="1.0.0",
        docs_url="/swagger",
        redoc_url="/api",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
    app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])

    return app
```

---

## APIRouter

```python
# api/routes/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from api.dependencies import get_current_user, get_db_session
from api.schemas.users import UserResponse, CreateUserRequest
from domain.use_cases.users import CreateUserUseCase
from domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    session=Depends(get_db_session),
):
    return await UserCRUD(session).list(skip=skip, limit=limit)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    use_case: CreateUserUseCase = Depends(get_create_user_use_case),
):
    return await use_case.execute(body)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, session=Depends(get_db_session)):
    user = await UserCRUD(session).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    _current_user: User = Depends(get_current_user),  # requires auth
    session=Depends(get_db_session),
):
    await UserCRUD(session).delete(user_id)
```

---

## Dependency Injection

```python
# api/dependencies.py
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from config.dependencies import GlobalDependencies


async def get_db_session() -> AsyncSession:
    async with GlobalDependencies.db_engine.begin() as session:
        yield session  # yields inside with-block; rolls back on exception


async def get_api_key(x_api_key: str = Header(...)) -> str:
    if x_api_key not in GlobalDependencies.valid_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    payload = decode_jwt(token)               # raises 401 on bad token
    user = await UserCRUD(session).get(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# Chain dependencies — get_create_user_use_case depends on get_db_session
def get_create_user_use_case(
    session: AsyncSession = Depends(get_db_session),
) -> CreateUserUseCase:
    return CreateUserUseCase(repo=UserRepo(session))
```

**Key rules:**
- `yield`-based dependencies run cleanup after the response is sent
- FastAPI caches dependencies within a single request — `get_db_session` called 3 times in one request returns the same session
- Use `Depends(get_current_user)` as a parameter to require auth on a route

---

## Pydantic v2 Schemas

```python
# api/schemas/users.py
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from datetime import datetime
from typing import Annotated

UserId = Annotated[str, Field(min_length=1, description="User UUID")]


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    role: Literal["admin", "user"] = "user"
    age: int = Field(ge=0, le=150)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def admin_must_have_age(self) -> "CreateUserRequest":
        if self.role == "admin" and self.age < 18:
            raise ValueError("Admins must be 18+")
        return self


class UserResponse(BaseModel):
    id: UserId
    name: str
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)  # allows ORM → schema conversion


# Nested schemas
class OrderWithUserResponse(BaseModel):
    id: str
    total: float
    user: UserResponse             # nested
    items: list[OrderItemResponse]
```

---

## Settings (Pydantic Settings)

```python
# config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str
    redis_url: str = "redis://localhost:6379"
    secret_key: str
    allowed_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

# In dependency:
def get_settings_dep(settings: Settings = Depends(get_settings)) -> Settings:
    return settings
```

---

## Error Handling

```python
# domain/exceptions.py
class ClientError(Exception):
    """400 — bad input, caller's fault"""
    def __init__(self, message: str): self.message = message

class NotFoundError(Exception):
    """404"""
    def __init__(self, resource: str, id: str):
        self.message = f"{resource} '{id}' not found"

class ServiceError(Exception):
    """500 — internal failure"""


# api/app.py — register handlers
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(ClientError)
async def client_error_handler(request: Request, exc: ClientError):
    return JSONResponse(status_code=400, content={"detail": exc.message})

@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": exc.message})

@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    return JSONResponse(status_code=500, content={"detail": "Internal error"})
```

Never raise `HTTPException` inside use cases — only in route handlers or dependencies.

---

## Middleware

```python
# api/middleware.py
import uuid, time
from fastapi import Request

async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    response.headers["x-request-id"] = request_id
    response.headers["x-response-time"] = f"{duration:.3f}s"
    return response

# Register as BaseHTTPMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
app.add_middleware(BaseHTTPMiddleware, dispatch=request_id_middleware)
```

---

## Background Tasks

```python
from fastapi import BackgroundTasks

@router.post("/users/")
async def create_user(
    body: CreateUserRequest,
    background_tasks: BackgroundTasks,
    session=Depends(get_db_session),
):
    user = await UserCRUD(session).create(body)
    # runs after response is sent — good for emails, webhooks, cache invalidation
    background_tasks.add_task(send_welcome_email, user.email, user.name)
    return user
```

Use background tasks for fire-and-forget work. For durable/retryable work, use a task queue (Celery, ARQ, Temporal).

---

## Authentication (JWT + OAuth2)

```python
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

@router.post("/auth/token")
async def login(form: OAuth2PasswordRequestForm = Depends(), session=Depends(get_db_session)):
    user = await authenticate_user(form.username, form.password, session)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect credentials",
                            headers={"WWW-Authenticate": "Bearer"})
    token = jwt.encode(
        {"sub": user.id, "exp": datetime.utcnow() + timedelta(hours=24)},
        settings.secret_key, algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer"}


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    ...
```

---

## WebSockets

```python
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, ws: WebSocket):
        await ws.accept()
        self.connections[client_id] = ws

    def disconnect(self, client_id: str):
        self.connections.pop(client_id, None)

    async def broadcast(self, message: str):
        for ws in self.connections.values():
            await ws.send_text(message)

manager = ConnectionManager()

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"{client_id}: {data}")
    except WebSocketDisconnect:
        manager.disconnect(client_id)
```

---

## Testing

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from api.app import create_app

@pytest.fixture
def app():
    return create_app()

@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# tests/test_users.py
@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    response = await client.post("/api/v1/users/", json={
        "name": "Alice",
        "email": "alice@example.com",
        "role": "user",
        "age": 30,
    })
    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"

@pytest.mark.asyncio
async def test_get_missing_user(client: AsyncClient):
    response = await client.get("/api/v1/users/nonexistent")
    assert response.status_code == 404

# Override dependencies in tests
from api.dependencies import get_current_user
app.dependency_overrides[get_current_user] = lambda: fake_user
```

---

## Red Flags

- **Business logic in route handlers** — handlers that do more than parse input, call a service, and return a response become untestable; keep handlers thin and domain logic in service layers
- **Multiple `Depends()` each creating their own DB session** — separate session per dependency in one request can lead to inconsistent reads; use a single session factory via a shared lifespan dependency
- **`BackgroundTasks` for work that must not be lost** — `BackgroundTasks` run in-process and die with the worker on crash or restart; use a proper job queue (Celery, ARQ) for durable background work
- **Pydantic models shared between API and DB layers** — using the same model for request validation and ORM mapping couples the API contract to the DB schema; maintain separate schemas for each layer
- **SDK clients or DB pools initialized at module level without lifespan** — module-level initialization prevents proper startup/shutdown and breaks test isolation; use the `@asynccontextmanager` lifespan pattern
- **`HTTPException` raised from service or domain layers** — HTTP exceptions in business logic couple the domain to the web framework; raise domain exceptions and map them to HTTP responses at the route layer
- **`response_model` omitted on endpoints returning ORM objects** — without `response_model`, FastAPI serializes the full ORM object including internal fields; always declare `response_model` to control the response schema

## Checklist

- [ ] Routes delegate to use cases — no business logic in route handlers
- [ ] Use cases raise domain exceptions (`ClientError`, `NotFoundError`) — not `HTTPException`
- [ ] Exception handlers in `app.py` convert domain exceptions to HTTP responses
- [ ] `yield`-based dependencies used for DB sessions (ensures cleanup)
- [ ] Pydantic schemas separate from ORM models — conversion in adapter layer
- [ ] Settings loaded via `pydantic-settings` from env / `.env` file
- [ ] Background tasks used only for fire-and-forget (use task queue for retryable work)
- [ ] Tests use `AsyncClient` with `ASGITransport` — not `TestClient` for async routes
- [ ] `dependency_overrides` used in tests instead of mocking internals
