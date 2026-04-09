Audit code against the security skill checklist and OWASP best practices.

## Instructions

1. Determine scope:
   - If the user specifies files/directories, scan those
   - If no scope given, scan `git diff` (staged + unstaged changes)
   - If no changes, scan the `src/` directory

2. For each file in scope, check against these categories:

### A. Injection (OWASP A03)
- [ ] SQL queries use parameterized statements, not string concatenation
- [ ] No `eval()`, `exec()`, `Function()` with dynamic input
- [ ] No `shell=True` or backtick execution with user input
- [ ] Template rendering uses auto-escaping (XSS prevention)
- [ ] LDAP, XML, and OS command inputs are sanitized

### B. Authentication & Session (OWASP A07)
- [ ] Passwords hashed with bcrypt/scrypt/argon2 (not MD5/SHA1)
- [ ] Session tokens are cryptographically random, sufficient length
- [ ] JWT secrets are not hardcoded
- [ ] Token expiration is enforced
- [ ] Failed login attempts are rate-limited

### C. Authorization (OWASP A01)
- [ ] Every endpoint checks authorization, not just authentication
- [ ] Resource access verifies ownership (IDOR prevention)
- [ ] Admin endpoints have explicit role checks
- [ ] No privilege escalation through parameter manipulation
- [ ] Default deny — new endpoints require explicit permission grants

### D. Data Exposure (OWASP A02)
- [ ] No hardcoded secrets, API keys, passwords, or tokens
- [ ] Sensitive data not logged (passwords, tokens, PII)
- [ ] Error responses don't leak stack traces or internal paths
- [ ] PII is encrypted at rest
- [ ] API responses don't over-expose fields (use DTOs/serializers)

### E. Security Misconfiguration (OWASP A05)
- [ ] CORS is restrictive (not `*` in production)
- [ ] Security headers set (CSP, HSTS, X-Frame-Options, etc.)
- [ ] Debug mode disabled in production configs
- [ ] Default credentials changed
- [ ] Unnecessary HTTP methods disabled

### F. Dependencies (OWASP A06)
- [ ] No known vulnerable dependencies (check lock files)
- [ ] Dependencies are pinned to specific versions
- [ ] No unnecessary dependencies with large attack surface

### G. Cryptography (OWASP A02)
- [ ] Using current algorithms (AES-256, RSA-2048+, SHA-256+)
- [ ] No custom crypto implementations
- [ ] Random number generation uses crypto-safe PRNG
- [ ] TLS 1.2+ enforced for external connections

3. Also scan for secrets using pattern matching:
   - API keys: patterns like `AKIA`, `sk-`, `ghp_`, `Bearer `
   - Private keys: `-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----`
   - Connection strings: `postgres://`, `mongodb://`, `redis://` with passwords
   - Generic patterns: `password\s*=`, `secret\s*=`, `token\s*=` with string values

4. Output the report:

```
## Security Scan Report
**Scope:** {files/directories scanned}
**Files scanned:** {count}
**Date:** {YYYY-MM-DD}

## Findings

### 🔴 Critical (must fix before merge)
- [file:line] {description} — {OWASP category}

### 🟠 High (fix soon)
- [file:line] {description} — {OWASP category}

### 🟡 Medium (should fix)
- [file:line] {description} — {OWASP category}

### 🔵 Low / Informational
- [file:line] {description}

## Secrets Scan
- {status: PASS or list of potential secrets found}

## Recommendations
1. {highest priority recommendation}
2. {next recommendation}

## Not Checked (out of scope for static analysis)
- Runtime behavior, network configuration, cloud IAM policies
- Dynamic analysis (fuzzing, DAST)
```

5. If no issues found, clearly state the code passes all static checks.

## Output
- Structured security report with severity-rated findings
- Specific file:line references for each issue
- Actionable fix recommendations
