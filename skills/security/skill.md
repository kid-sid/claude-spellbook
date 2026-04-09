---
name: security
description: "Application security: OWASP Top 10 mitigations, JWT and OAuth2/OIDC authentication patterns, RBAC/ABAC authorization, secrets management (env vars to Vault), input validation and injection prevention, security headers, STRIDE threat modeling, and dependency scanning for Python, TypeScript, and Go."
---

# Security

A comprehensive reference for securing backend APIs and web applications — covering authentication, authorization, secrets, input validation, security headers, threat modeling, and dependency hygiene across Python, TypeScript, and Go.

## When to Activate

- Implementing authentication or session management
- Reviewing code for security vulnerabilities or injection risks
- Handling secrets, API keys, or credentials in code or config
- Designing authorization — who can access what
- Configuring security headers for an API or web application
- Setting up dependency scanning in CI
- Running a threat model for a new feature or system

## OWASP Top 10 Quick Reference

| # | Vulnerability | Description | Primary Mitigation |
|---|--------------|-------------|-------------------|
| A01 | Broken Access Control | Users act outside intended permissions | Enforce ownership checks server-side on every request |
| A02 | Cryptographic Failures | Sensitive data exposed due to weak/absent encryption | TLS everywhere, strong hashing, encrypted secrets at rest |
| A03 | Injection | Hostile data sent to an interpreter | Parameterized queries, input validation, output encoding |
| A04 | Insecure Design | Missing or ineffective security controls in the design | Threat modeling, secure design patterns, abuse case review |
| A05 | Security Misconfiguration | Insecure defaults, open cloud storage, verbose errors | Harden configs, disable defaults, suppress stack traces in prod |
| A06 | Vulnerable Components | Using components with known vulnerabilities | Dependency scanning in CI, automated updates via Renovate/Dependabot |
| A07 | ID & Auth Failures | Weak authentication, credential stuffing, broken session management | MFA, secure password hashing, session invalidation, rate limiting |
| A08 | Software/Data Integrity Failures | Unsigned updates, insecure deserialization, CI/CD tampering | Verify supply chain, sign artifacts, restrict pipeline permissions |
| A09 | Logging & Monitoring Failures | Insufficient logging to detect breaches | Structured audit logs, alerting on anomalies, log retention policy |
| A10 | SSRF | Server fetches attacker-controlled URL | Allowlist destinations, block internal address ranges (169.254.x.x, 10.x.x.x) |

### Injection (A03) — Deep Dive

Never construct queries or commands by concatenating user input.

**SQL Injection**

```python
# BAD — string concatenation opens SQLi
query = f"SELECT * FROM users WHERE email = '{user_input}'"
cursor.execute(query)

# GOOD — parameterized query
cursor.execute("SELECT * FROM users WHERE email = %s", (user_input,))
```

```typescript
// BAD
const rows = await db.query(`SELECT * FROM users WHERE email = '${userInput}'`);

// GOOD
const rows = await db.query("SELECT * FROM users WHERE email = $1", [userInput]);
```

```go
// BAD
row := db.QueryRow("SELECT * FROM users WHERE email = '" + userInput + "'")

// GOOD
row := db.QueryRow("SELECT * FROM users WHERE email = ?", userInput)
```

**Command Injection**

```python
# BAD — shell=True with user input is always dangerous
import subprocess
subprocess.run(f"convert {filename}", shell=True)

# GOOD — pass args as a list, shell=False (default)
subprocess.run(["convert", filename])
```

```typescript
// BAD
exec(`convert ${filename}`);

// GOOD — use execFile with an array of arguments
import { execFile } from "child_process";
execFile("convert", [filename]);
```

```go
// BAD
cmd := exec.Command("sh", "-c", "convert "+filename)

// GOOD
cmd := exec.Command("convert", filename)
```

### Broken Access Control (A01) — Deep Dive

Check ownership at the handler level, not only role membership. A role check alone prevents vertical privilege escalation (a regular user doing admin things) but not horizontal privilege escalation (a user accessing another user's resources — IDOR).

**IDOR (Insecure Direct Object Reference)**

```python
# BAD — checks auth, but not ownership
@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, current_user=Depends(get_current_user)):
    return db.query(Invoice).filter(Invoice.id == invoice_id).first()

# GOOD — verifies the resource belongs to the caller
@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, current_user=Depends(get_current_user)):
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.owner_id == current_user.id,  # ownership check
    ).first()
    if not invoice:
        raise HTTPException(status_code=404)
    return invoice
```

| Escalation Type | Description | Example |
|-----------------|-------------|---------|
| Vertical | Lower-privileged user accesses higher-privileged functions | Regular user calls admin endpoint |
| Horizontal | User accesses another user's data at the same privilege level | User A reads User B's invoices via IDOR |

### Security Misconfiguration (A05) — Deep Dive

- Remove default credentials immediately (database root passwords, admin/admin panels).
- Suppress stack traces in production — return generic error messages, log details server-side.
- Audit S3 bucket ACLs: `aws s3api get-bucket-acl --bucket <name>` — buckets must never be `public-read` or `public-read-write` unless serving static public assets intentionally.
- CORS must allowlist specific origins; `Access-Control-Allow-Origin: *` disables same-origin protection for all browsers.

## Authentication Patterns

### Password Hashing

Never store plaintext passwords or hashes produced by MD5, SHA-1, or unsalted SHA-256. Use a slow, adaptive hashing algorithm: `bcrypt` (work factor ≥ 12) or `argon2id`.

```python
# Python — bcrypt via passlib
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

hashed = pwd_context.hash("user_plaintext_password")
valid  = pwd_context.verify("user_plaintext_password", hashed)
```

```typescript
// TypeScript — bcryptjs
import bcrypt from "bcryptjs";

const hashed = await bcrypt.hash(plaintext, 12);       // work factor 12
const valid  = await bcrypt.compare(plaintext, hashed);
```

```go
// Go — golang.org/x/crypto/bcrypt
import "golang.org/x/crypto/bcrypt"

hashed, err := bcrypt.GenerateFromPassword([]byte(plaintext), 12)
err = bcrypt.CompareHashAndPassword(hashed, []byte(plaintext))
```

### JWT (JSON Web Tokens)

**Structure:** `Base64URL(header).Base64URL(payload).signature`

**Signing algorithm choice:**

| Algorithm | Key Type | Use Case |
|-----------|----------|----------|
| RS256 | RSA key pair (asymmetric) | Microservices — verify without sharing secret; preferred |
| HS256 | Shared secret (symmetric) | Single-service — simpler, but secret must be shared to verify |
| ES256 | ECDSA key pair (asymmetric) | Same as RS256 but smaller tokens |

**Required claims:** `iss` (issuer), `sub` (subject/user ID), `aud` (audience), `exp` (expiry unix timestamp), `iat` (issued-at unix timestamp).

**Token storage:**

```html
<!-- BAD — localStorage is readable by any JavaScript on the page (XSS risk) -->
localStorage.setItem("access_token", token);

<!-- GOOD — httpOnly cookie is inaccessible to JavaScript -->
<!-- Set by server: Set-Cookie: access_token=<jwt>; HttpOnly; Secure; SameSite=Strict -->
```

**Refresh token rotation:** Issue a short-lived access token (15 min) alongside a long-lived refresh token (7 days). On each refresh, invalidate the old refresh token and issue a new one. Detect token reuse — if a refresh token is used twice, revoke the entire family.

**JWT verification — all 3 languages:**

```python
# Python — PyJWT
import jwt

payload = jwt.decode(
    token,
    public_key,           # RS256: public key; HS256: shared secret
    algorithms=["RS256"],
    audience="my-api",
    options={"require": ["exp", "iss", "sub", "aud"]},
)
```

```typescript
// TypeScript — jose
import { jwtVerify } from "jose";

const { payload } = await jwtVerify(token, publicKey, {
  issuer: "https://auth.example.com",
  audience: "my-api",
});
```

```go
// Go — golang-jwt/jwt
import "github.com/golang-jwt/jwt/v5"

token, err := jwt.Parse(tokenString, func(t *jwt.Token) (interface{}, error) {
    if _, ok := t.Method.(*jwt.SigningMethodRSA); !ok {
        return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
    }
    return publicKey, nil
}, jwt.WithAudience("my-api"), jwt.WithIssuer("https://auth.example.com"))
```

### Session-Based Auth

For server-rendered applications, server-side sessions (stored in Redis or a database) are a simpler and often safer alternative to JWTs.

Set all three protective cookie flags:

```http
Set-Cookie: session_id=<opaque_id>; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=3600
```

| Flag | Effect |
|------|--------|
| `HttpOnly` | Cookie inaccessible to JavaScript — blocks XSS token theft |
| `Secure` | Cookie sent only over HTTPS |
| `SameSite=Strict` | Cookie not sent on cross-site requests — blocks CSRF |

## OAuth2 / OIDC

### Flow Selection

| Flow | Use Case | PKCE Required |
|------|----------|---------------|
| Authorization Code + PKCE | Browser SPA, mobile/native apps | Yes |
| Client Credentials | Machine-to-machine (M2M), backend services | No — uses client secret |
| Device Code | CLI tools, smart TV apps | No — polling-based |

### Authorization Code + PKCE Steps

1. App generates a cryptographically random `code_verifier` (43–128 chars).
2. App computes `code_challenge = BASE64URL(SHA256(code_verifier))`.
3. App redirects user to IdP authorization URL with `code_challenge` and `code_challenge_method=S256`.
4. User authenticates at IdP; IdP redirects back with `authorization_code`.
5. App exchanges `authorization_code` + `code_verifier` (not the challenge) at token endpoint.
6. IdP verifies `SHA256(code_verifier) == code_challenge` stored from step 3, then returns tokens.
7. App stores access token in `httpOnly` cookie; never in `localStorage`.

### Build vs Buy

Use a third-party IdP (Auth0, Clerk, Cognito, Okta) unless you have exceptional requirements. Rolling your own OAuth2/OIDC server is a multi-month project with serious security risk surface: token endpoint, PKCE, refresh rotation, MFA, brute-force protection, RBAC, and audit logging all need to be correct simultaneously.

### Scope Design

```
# BAD — wildcard and coarse scopes leak excessive access
scopes: ["admin", "*", "readwrite"]

# GOOD — narrow, resource-specific scopes
scopes: ["read:invoices", "write:invoices", "read:profile"]
```

Never grant `admin` or wildcard scopes to third-party integrations. Use the principle of least privilege — request only the scopes needed for the operation.

## Authorization Patterns

### RBAC vs ABAC

| Dimension | RBAC | ABAC |
|-----------|------|------|
| Definition | Permissions assigned to roles; users assigned to roles | Permissions derived from attributes of user, resource, environment |
| Complexity | Low — simple to implement and audit | High — policy engine required (OPA, Casbin) |
| Flexibility | Low — coarse-grained; role explosion at scale | High — fine-grained contextual decisions |
| Best For | Small teams, well-defined job functions | Multi-tenant SaaS, dynamic access policies, data-level isolation |

### Resource-Level Authorization

Check ownership in the handler, not only in middleware. Middleware can verify the token is valid and extract the role — it cannot verify the requested resource belongs to the caller.

```typescript
// BAD — only checks role, not resource ownership
router.delete("/posts/:id", requireRole("user"), async (req, res) => {
  await db.posts.delete({ where: { id: req.params.id } });
  res.sendStatus(204);
});

// GOOD — verifies caller owns the resource before deleting
router.delete("/posts/:id", requireRole("user"), async (req, res) => {
  const post = await db.posts.findUnique({ where: { id: req.params.id } });
  if (!post) return res.sendStatus(404);
  if (post.authorId !== req.user.id) return res.sendStatus(403); // ownership check
  await db.posts.delete({ where: { id: req.params.id } });
  res.sendStatus(204);
});
```

### Policy Object Pattern

For complex logic, encapsulate authorization decisions in a policy object rather than scattering `if` checks across handlers.

```python
class PostPolicy:
    def can_edit(self, user, post) -> bool:
        return post.author_id == user.id or user.role == "admin"

    def can_delete(self, user, post) -> bool:
        return post.author_id == user.id or user.role == "admin"

    def can_publish(self, user, post) -> bool:
        return user.role in ("editor", "admin")

# Handler
policy = PostPolicy()
if not policy.can_edit(current_user, post):
    raise PermissionError("Forbidden")
```

### Common Authorization Mistakes

- Checking permissions only in the UI — API endpoints are directly reachable; always enforce server-side.
- Enforcing access control on reads but not on writes — verify on every create, update, and delete.
- Relying on obscurity — never assume an endpoint is safe because it is undocumented.
- Missing re-authorization after role changes — invalidate sessions or tokens when a user's role is downgraded.

## Secrets Management

The rule: never commit secrets. A `.env` file is for local development only — add it to `.gitignore` and never commit it to version control.

```python
# BAD — hardcoded secret in source code
SECRET_KEY = "sk_live_abc123supersecretkey"
DATABASE_URL = "postgres://admin:password123@prod-db/app"

# GOOD — read from environment at runtime
import os
SECRET_KEY  = os.environ["SECRET_KEY"]
DATABASE_URL = os.environ["DATABASE_URL"]
```

### Secrets Progression by Environment

| Environment | Secret Storage | Notes |
|-------------|---------------|-------|
| Local Dev | `.env` file (gitignored) | Never commit; use `.env.example` with fake values for documentation |
| CI (GitHub Actions) | Repository or org Secrets (`${{ secrets.NAME }}`) | Masked in logs; scoped to workflows |
| CI (GitLab) | CI/CD Variables (masked, protected) | Mark variables as masked to prevent log exposure |
| Production | HashiCorp Vault / AWS Secrets Manager / GCP Secret Manager / Doppler | Dynamic secrets, audit trail, automatic rotation |

### Secret Rotation

- Never reuse secrets across services or environments.
- Rotate immediately on suspected exposure — treat exposure as confirmed until proven otherwise.
- Automate rotation where the provider supports it (AWS RDS credentials via Secrets Manager, Vault dynamic secrets).
- After rotation, verify all consumers are updated before invalidating the old secret.

### Required `.gitignore` Entries

```gitignore
.env
.env.*
!.env.example
*.pem
*.key
*.p12
credentials.json
serviceAccountKey.json
.aws/credentials
kubeconfig
terraform.tfvars
```

## Input Validation and Injection Prevention

### Parameterized Queries

Always use parameterized queries or an ORM with parameter binding. No exceptions for "safe" input — the validation layer can be bypassed.

```python
# BAD
cursor.execute("INSERT INTO orders (user_id, item) VALUES ('" + user_id + "', '" + item + "')")

# GOOD — psycopg2 / SQLAlchemy
cursor.execute("INSERT INTO orders (user_id, item) VALUES (%s, %s)", (user_id, item))
```

```typescript
// BAD
await pool.query(`INSERT INTO orders (user_id, item) VALUES ('${userId}', '${item}')`);

// GOOD — pg / Prisma / Drizzle
await pool.query("INSERT INTO orders (user_id, item) VALUES ($1, $2)", [userId, item]);
```

```go
// BAD
db.Exec("INSERT INTO orders (user_id, item) VALUES ('" + userID + "', '" + item + "')")

// GOOD
db.Exec("INSERT INTO orders (user_id, item) VALUES (?, ?)", userID, item)
```

### File Upload Validation

```python
import magic  # python-magic (libmagic binding)

ALLOWED_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

def validate_upload(file_bytes: bytes, claimed_extension: str) -> None:
    if len(file_bytes) > MAX_SIZE_BYTES:
        raise ValueError("File too large")
    detected_mime = magic.from_buffer(file_bytes, mime=True)
    if detected_mime not in ALLOWED_TYPES:
        raise ValueError(f"File type not allowed: {detected_mime}")
    # Store to a path outside the web root — never serve raw uploads directly
```

Key rules:
- Detect MIME type from file content (magic bytes), not from the file extension or `Content-Type` header.
- Enforce a maximum size before reading the full payload into memory.
- Store uploaded files outside the web root or in object storage, never in a publicly served directory.
- Rename files on storage — never preserve the user-supplied filename.

### HTML Output Escaping

```typescript
// BAD — executes arbitrary JS if userInput contains <script>...</script>
element.innerHTML = userInput;

// GOOD — use textContent for plain text
element.textContent = userInput;

// GOOD — for rich HTML, use a sanitizer library
import DOMPurify from "dompurify";
element.innerHTML = DOMPurify.sanitize(userInput);
```

Use auto-escaping templating engines (Jinja2, Go `html/template`, React JSX) — they escape by default. Only bypass escaping intentionally with `| safe` / `dangerouslySetInnerHTML` and only on content you fully control.

### Validation Libraries

| Language | Library | Notes |
|----------|---------|-------|
| Python | `pydantic` | Schema-first; validates at parse time; ideal for FastAPI |
| TypeScript | `zod` | Runtime schema validation; pairs well with `tRPC` |
| Go | `go-playground/validator` | Struct tag–based validation; widely used with Gin/Echo |

Validate at the API boundary — reject invalid input before it reaches business logic or the database.

## Security Headers

Set these headers on every HTTP response from your API or web server.

| Header | Recommended Value | What It Prevents |
|--------|------------------|-----------------|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; object-src 'none'` | XSS, data injection, resource hijacking |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | SSL stripping, MITM downgrade attacks |
| `X-Frame-Options` | `DENY` | Clickjacking via iframe embedding |
| `X-Content-Type-Options` | `nosniff` | MIME-type sniffing attacks |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Referrer URL leakage to third parties |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Unauthorized browser feature access |
| `Cache-Control` | `no-store` (for authenticated endpoints) | Sensitive data cached in shared proxies |

**CORS configuration:**

```python
# BAD — allows any origin to make credentialed requests
CORS(app, origins="*", supports_credentials=True)

# GOOD — explicit allowlist; never wildcard for authenticated routes
CORS(app, origins=["https://app.example.com", "https://admin.example.com"])
```

`Access-Control-Allow-Origin: *` is acceptable only for fully public, unauthenticated endpoints (e.g., a public API with no user data). Never combine `*` with `Access-Control-Allow-Credentials: true` — browsers reject it, and it would be a severe security flaw if they did not.

### Adding Headers in Each Language

```python
# FastAPI — middleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
```

```typescript
// Express — use helmet
import helmet from "helmet";
app.use(helmet());  // sets all recommended headers with sane defaults
```

```go
// Go — net/http middleware
func securityHeaders(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("X-Content-Type-Options", "nosniff")
        w.Header().Set("X-Frame-Options", "DENY")
        w.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        next.ServeHTTP(w, r)
    })
}
```

## STRIDE Threat Modeling

### STRIDE Reference Table

| Threat | Description | Mitigation Category |
|--------|-------------|-------------------|
| Spoofing | Claiming an identity you do not own | Authentication — verify identity on every request |
| Tampering | Modifying data in transit or at rest without authorization | Integrity — TLS, HMAC signing, database audit logs |
| Repudiation | Denying that an action occurred | Audit logging — immutable, attributable event records |
| Information Disclosure | Exposing sensitive data to unauthorized parties | Encryption at rest and in transit, access control, minimal data exposure |
| Denial of Service | Making the system unavailable to legitimate users | Rate limiting, resource quotas, circuit breakers, auto-scaling |
| Elevation of Privilege | Gaining capabilities beyond what is authorized | Authorization checks on every operation, principle of least privilege |

### Threat Modeling Process

1. **Draw a data flow diagram (DFD).** Identify every external entity, process, data store, and data flow in the feature.
2. **Mark trust boundaries.** A trust boundary is crossed wherever data moves between different trust levels — browser to API, API to database, service to third-party, internal service to internal service.
3. **Apply STRIDE to each data flow and process.** For each element, ask: can it be Spoofed? Tampered? Repudiated? Disclosed? Denied? Escalated?
4. **List mitigations.** For each identified threat, record the control that addresses it (or note that it is accepted risk with justification).
5. **Re-review when the design changes.** A threat model is not a one-time artifact — revisit it when auth, data flows, or trust boundaries change.

**Lightweight threat model template:**

| Data Flow | STRIDE Threats Identified | Mitigation |
|-----------|--------------------------|------------|
| Browser → API (login) | Spoofing (credential stuffing), DoS (brute force) | Rate limit login endpoint, MFA, account lockout |
| API → Database | Injection (A03), Information Disclosure | Parameterized queries, least-privilege DB user |
| API → Third-party payment service | Tampering (webhook), Repudiation | Verify webhook HMAC signature, log all events |
| S3 presigned URL → Browser | Information Disclosure | Short-lived URLs (15 min), bucket policy denies public access |

## Dependency Scanning

### Tools by Language

| Language | Tool | Purpose |
|----------|------|---------|
| Python | `pip-audit` | Scans installed packages against OSV/PyPI advisory database |
| Python | `safety` | CVE scanning; integrates with CI |
| Python | Dependabot | Automated PRs for vulnerable package updates |
| TypeScript | `npm audit` | Built-in; checks against npm advisory database |
| TypeScript | `socket.dev` | Supply chain analysis — detects typosquatting and malicious packages |
| TypeScript | Snyk | CVE scanning with fix PRs |
| Go | `govulncheck` | Official Go vulnerability scanner from the Go team; checks call graph |

### CI Integration

```yaml
# GitHub Actions — Python
- name: Scan dependencies
  run: pip-audit --strict --vulnerability-service osv

# GitHub Actions — TypeScript
- name: Scan dependencies
  run: npm audit --audit-level=high

# GitHub Actions — Go
- name: Scan dependencies
  run: |
    go install golang.org/x/vuln/cmd/govulncheck@latest
    govulncheck ./...
```

Fail the CI build on HIGH or CRITICAL severity findings. Treat a new HIGH CVE in a direct dependency the same as a failing test — it blocks the merge.

### Automated Dependency Updates

Configure Dependabot (`/.github/dependabot.yml`) or Renovate to open automated PRs when dependency updates are available. Keep the update cadence short (weekly) to avoid large, risky batch upgrades.

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
  - package-ecosystem: npm
    directory: "/"
    schedule:
      interval: weekly
  - package-ecosystem: gomod
    directory: "/"
    schedule:
      interval: weekly
```

### SBOM Generation

Generate a Software Bill of Materials for auditing and compliance.

```bash
# Python
pip install cyclonedx-bom
cyclonedx-py environment -o sbom.json

# TypeScript
npx @cyclonedx/cyclonedx-npm --output-file sbom.json

# Go
go install github.com/CycloneDX/cyclonedx-gomod/cmd/cyclonedx-gomod@latest
cyclonedx-gomod app -output sbom.json
```

## Checklist

- [ ] Passwords hashed with bcrypt (factor 12+) or argon2id — never MD5/SHA1/plaintext
- [ ] JWT signed with RS256 (asymmetric) or HS256 with strong secret (32+ random bytes)
- [ ] Access tokens short-lived (15 min max); refresh tokens rotate on every use
- [ ] Secrets stored in vault/secrets manager in production — never in env files committed to git
- [ ] `.gitignore` covers `.env`, `*.pem`, `*.key`, `credentials.json`, `serviceAccountKey.json`
- [ ] All SQL queries use parameterized statements — no string concatenation with user input
- [ ] User input validated at the API boundary with pydantic / zod / go-playground/validator
- [ ] Authorization checks resource ownership (`resource.owner_id == current_user.id`), not just role
- [ ] Authorization enforced on create, update, and delete — not only on read
- [ ] Security headers set on all API and web responses (CSP, HSTS, X-Frame-Options, nosniff)
- [ ] CORS configured to allowlist specific origins — no wildcard `*` on authenticated routes
- [ ] Dependency scanner runs in CI and fails the build on HIGH/CRITICAL CVEs
- [ ] No stack traces or internal error details exposed in production API responses
- [ ] File uploads validated by MIME type (magic bytes), size limit enforced, stored outside web root
- [ ] Threat model reviewed for any new feature touching authentication, authorization, or sensitive data
