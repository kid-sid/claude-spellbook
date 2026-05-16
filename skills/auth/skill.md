---
name: auth
description: Use when implementing login flows, issuing or validating JWTs, setting up OAuth2/OIDC with a provider, designing role-based or attribute-based access control, securing API endpoints, or handling token refresh and revocation.
---

# Authentication & Authorization

Patterns for identity, token management, and access control across web APIs and services.

## When to Activate

- Implementing login, logout, or registration flows
- Issuing, validating, or refreshing JWTs
- Integrating an OAuth2/OIDC provider (Google, GitHub, Auth0, Keycloak)
- Designing role-based (RBAC) or attribute-based (ABAC) access control
- Securing REST or GraphQL endpoints with middleware/guards
- Handling token revocation, rotation, or blacklisting
- Auditing an existing auth implementation for security gaps

---

## Core Concepts

### Authentication vs. Authorization

| Concept | Question answered | Example |
|---|---|---|
| Authentication | Who are you? | Login with email + password |
| Authorization | What can you do? | Admin can delete; viewer can only read |
| Identity | What do we know about you? | Email, roles, tenant ID in the token |

### Token Types

| Type | Storage | Lifespan | Use for |
|---|---|---|---|
| Access token (JWT) | Memory / header | 5–60 min | API calls |
| Refresh token (opaque) | HttpOnly cookie | Days–weeks | Obtain new access tokens |
| Session cookie | HttpOnly cookie | Session or sliding | Traditional web apps |
| API key | Server-side only | Long-lived | M2M, developer integrations |

---

## JWT Patterns

### Structure and Signing

```python
# Python — PyJWT
import jwt
from datetime import datetime, timedelta, UTC

SECRET = "..."  # use RS256 with a key pair in production

def issue_token(user_id: str, roles: list[str]) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "roles": roles,
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=15),
        },
        SECRET,
        algorithm="HS256",
    )

def verify_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"])
```

```typescript
// TypeScript — jose
import { SignJWT, jwtVerify } from "jose";

const secret = new TextEncoder().encode(process.env.JWT_SECRET);

async function issueToken(userId: string, roles: string[]): Promise<string> {
  return new SignJWT({ sub: userId, roles })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("15m")
    .sign(secret);
}

async function verifyToken(token: string) {
  const { payload } = await jwtVerify(token, secret);
  return payload;
}
```

```go
// Go — golang-jwt/jwt
import (
    "github.com/golang-jwt/jwt/v5"
    "time"
)

type Claims struct {
    Roles []string `json:"roles"`
    jwt.RegisteredClaims
}

func IssueToken(userID string, roles []string, secret []byte) (string, error) {
    claims := Claims{
        Roles: roles,
        RegisteredClaims: jwt.RegisteredClaims{
            Subject:   userID,
            IssuedAt:  jwt.NewNumericDate(time.Now()),
            ExpiresAt: jwt.NewNumericDate(time.Now().Add(15 * time.Minute)),
        },
    }
    return jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString(secret)
}
```

### RS256 vs HS256

| | HS256 | RS256 |
|---|---|---|
| Key type | Shared secret | Private/public key pair |
| Who can verify | Anyone with the secret | Anyone with the public key |
| Best for | Single service | Microservices, public JWKS endpoint |
| Rotation | Requires coordinated redeploy | Rotate private key; publish new JWKS |

**Use RS256 in production** when multiple services verify tokens, or when tokens are issued by an identity provider.

---

## OAuth2 / OIDC

### Flow Selection

| Flow | Use when | Notes |
|---|---|---|
| Authorization Code + PKCE | Browser SPA, mobile app | No client secret on device |
| Authorization Code | Server-side web app | Store client secret server-side |
| Client Credentials | M2M / service accounts | No user involved |
| Device Code | CLI tools, smart TVs | User authenticates on a second device |

Never use Implicit flow — it is deprecated (RFC 9700).

### Authorization Code + PKCE (SPA)

```typescript
// 1. Generate PKCE values
function generateCodeVerifier(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return btoa(String.fromCharCode(...array)).replace(/[+/=]/g, (c) =>
    ({ "+": "-", "/": "_", "=": "" })[c]!
  );
}

async function generateCodeChallenge(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/[+/=]/g, (c) => ({ "+": "-", "/": "_", "=": "" })[c]!);
}

// 2. Redirect to provider
const verifier = generateCodeVerifier();
sessionStorage.setItem("pkce_verifier", verifier);
const challenge = await generateCodeChallenge(verifier);

const params = new URLSearchParams({
  response_type: "code",
  client_id: CLIENT_ID,
  redirect_uri: REDIRECT_URI,
  scope: "openid profile email",
  code_challenge: challenge,
  code_challenge_method: "S256",
  state: crypto.randomUUID(), // store and verify on return
});
window.location.href = `${PROVIDER_URL}/authorize?${params}`;

// 3. Exchange code for tokens (on redirect back)
async function handleCallback(code: string): Promise<void> {
  const verifier = sessionStorage.getItem("pkce_verifier")!;
  const res = await fetch(`${PROVIDER_URL}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: REDIRECT_URI,
      client_id: CLIENT_ID,
      code_verifier: verifier,
    }),
  });
  const { access_token, refresh_token, id_token } = await res.json();
  // store access_token in memory, refresh_token in HttpOnly cookie via backend
}
```

### Client Credentials (M2M)

```python
# Python — httpx
import httpx

def get_m2m_token(client_id: str, client_secret: str, token_url: str) -> str:
    r = httpx.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "api:read api:write",
        },
    )
    r.raise_for_status()
    return r.json()["access_token"]
```

---

## Token Storage

| Location | XSS safe | CSRF safe | Notes |
|---|---|---|---|
| Memory (JS variable) | Yes | Yes | Lost on page refresh; best for SPAs |
| HttpOnly cookie | Yes | No — add CSRF token | Best for refresh tokens |
| localStorage | No | Yes | Never store tokens here |
| sessionStorage | No | Yes | Cleared on tab close; still XSS-vulnerable |

**Rule:** Store access tokens in memory. Store refresh tokens in HttpOnly, SameSite=Strict cookies. Never put tokens in localStorage.

---

## Token Refresh and Revocation

### Silent Refresh Pattern

```typescript
let accessToken: string | null = null;

async function getValidToken(): Promise<string> {
  if (accessToken && !isExpiringSoon(accessToken)) return accessToken;

  const res = await fetch("/auth/refresh", {
    method: "POST",
    credentials: "include", // sends HttpOnly refresh token cookie
  });
  if (!res.ok) {
    // refresh token expired — redirect to login
    window.location.href = "/login";
    throw new Error("Session expired");
  }
  accessToken = (await res.json()).access_token;
  return accessToken;
}

function isExpiringSoon(token: string): boolean {
  const { exp } = JSON.parse(atob(token.split(".")[1]));
  return exp * 1000 - Date.now() < 60_000; // refresh if < 60s left
}
```

### Revocation Strategies

| Strategy | How | Trade-off |
|---|---|---|
| Short expiry | 5–15 min access tokens | No revocation needed; stale window is small |
| Token blacklist | Store revoked JTIs in Redis | Instant revocation; requires Redis lookup per request |
| Refresh token rotation | Issue new refresh token on each use; invalidate old | Detects theft; one-time-use tokens |
| Opaque tokens + introspection | Validate tokens against auth server | Instant revocation; adds latency |

---

## Access Control (RBAC / ABAC)

### RBAC Middleware

```python
# FastAPI
from functools import wraps
from fastapi import Depends, HTTPException, status
from typing import Callable

def require_roles(*roles: str) -> Callable:
    def dependency(token_data: dict = Depends(get_current_user)):
        user_roles = set(token_data.get("roles", []))
        if not user_roles.intersection(roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return token_data
    return dependency

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    _=Depends(require_roles("admin")),
):
    ...
```

```typescript
// Express middleware
function requireRoles(...roles: string[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    const userRoles: string[] = res.locals.user?.roles ?? [];
    if (!roles.some((r) => userRoles.includes(r))) {
      return res.status(403).json({ error: "Forbidden" });
    }
    next();
  };
}

router.delete("/users/:id", requireRoles("admin"), deleteUserHandler);
```

### ABAC Policy Check

```python
# Simple policy engine
def can(user: dict, action: str, resource: dict) -> bool:
    if "admin" in user["roles"]:
        return True
    if action == "read" and resource["public"]:
        return True
    if action in ("update", "delete") and resource["owner_id"] == user["id"]:
        return True
    return False

# Usage
if not can(current_user, "delete", post):
    raise HTTPException(status_code=403)
```

---

## Password Hashing

Always use a slow, salted hashing algorithm. Never use MD5, SHA-1, or SHA-256 for passwords.

| Algorithm | Library (Python) | Library (Node) | Recommended? |
|---|---|---|---|
| bcrypt | `bcrypt` | `bcrypt` / `argon2-browser` | Yes |
| Argon2id | `argon2-cffi` | `argon2-browser` | Yes — preferred |
| scrypt | stdlib `hashlib` | stdlib `crypto` | Yes |
| PBKDF2 | stdlib `hashlib` | stdlib `crypto` | Acceptable |
| MD5 / SHA-* | — | — | Never |

```python
# Python — argon2-cffi
from argon2 import PasswordHasher

ph = PasswordHasher()

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(hashed: str, password: str) -> bool:
    try:
        return ph.verify(hashed, password)
    except Exception:
        return False
```

---

## Red Flags

- **Storing tokens in localStorage** — XSS can steal every token; use HttpOnly cookies for refresh tokens and in-memory for access tokens.
- **Using HS256 across multiple services** — all services share the secret; a compromise of one exposes all; use RS256 with a JWKS endpoint.
- **Long-lived access tokens** — a 24-hour JWT cannot be revoked without a blacklist; keep them under 15 minutes.
- **Skipping `state` parameter in OAuth2** — omitting `state` enables CSRF attacks on the callback endpoint.
- **Rolling your own crypto** — never implement JWT signing, hashing, or encryption from scratch; use audited libraries.
- **Trusting the `alg` header from the token** — an attacker can set `alg: none`; always pin the algorithm server-side.
- **Returning 404 instead of 403** — security-by-obscurity doesn't prevent enumeration; return 403 Forbidden for authorization failures.
- **No token rotation on refresh** — refresh tokens that never rotate are permanent credentials; rotate on every use and invalidate the old one.
- **Putting secrets in JWTs** — JWTs are base64-encoded, not encrypted; any party with the token can read the payload.
- **Broad OAuth scopes** — request only the minimum scopes needed; `*` or `admin` scopes violate least privilege.

---

## Checklist

- [ ] Access tokens expire in 15 minutes or less
- [ ] Refresh tokens stored in HttpOnly, SameSite=Strict cookies — not localStorage
- [ ] Access tokens stored in memory only — never persisted to storage
- [ ] JWT algorithm pinned server-side — `alg: none` and algorithm-confusion attacks blocked
- [ ] OAuth2 `state` parameter generated, stored, and verified on callback
- [ ] PKCE used for all browser and mobile OAuth2 flows
- [ ] Passwords hashed with Argon2id or bcrypt — never SHA-* or MD5
- [ ] Refresh token rotation enabled — old token invalidated on each use
- [ ] Role/permission check applied at the handler level, not just the route group
- [ ] 401 returned for unauthenticated requests, 403 for unauthorized — never 404
- [ ] Sensitive claims (PII, internal IDs) not included in JWT payload
- [ ] HTTPS enforced on all auth endpoints — no token transmission over HTTP
- [ ] Rate limiting applied to login, register, and token endpoints
- [ ] Token revocation strategy documented and implemented (blacklist or short expiry)
