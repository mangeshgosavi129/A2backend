---
trigger: manual
description: Security standards based on OWASP Top 10 and ASVS.
---

# Security Rules & Standards

## 1. Authentication & Session Management
- **Protocol**: Use standard OAuth2 / OIDC flows. NEVER roll your own crypto or auth.
- **Tokens**:
    - Access tokens must be short-lived (e.g., 15-60 mins).
    - Refresh tokens must be creating using secure, httpOnly cookies where possible.
    - Never store tokens in localStorage (XSS risk).
- **Password Policy**: Enforce NIST guidelines (min 8 chars, no complexity rules, check against pwned passwords).

## 2. OWASP Top 10 Mitigation
You must actively defend against the following:

1.  **Broken Access Control**: Explicitly test that User A cannot access User B's data. Default to "deny all".
2.  **Cryptographic Failures**: Encrypt sensitive data at rest (AES-256) and in transit (TLS 1.2+).
3.  **Injection**: ALWAYS use parameterized queries (prepared statements). NEVER string-concatenate SQL.
4.  **Insecure Design**: Threat model critical features before implementation.
5.  **Security Misconfiguration**: Remove default passwords, disable debug features in prod.
6.  **Vulnerable Components**: Automatically scan dependencies (e.g., `pip-audit`, `npm audit`).
7.  **Identification and Authentication Failures**: Rate limit login attempts.
8.  **Software and Data Integrity Failures**: Verify digital signatures, ensure CI/CD pipeline integrity.
9.  **Security Logging and Monitoring Failures**: Log all auth failures (without passwords).
10. **SSRF**: Validate and sanitize all user-supplied URLs.

## 3. OWASP ASVS Checklist (Essential Subset)
For every feature, verify:

### Input Validation
- [ ] All input is validated against a whitelist of allowed characters, type, and length.
- [ ] All input is sanitized before use in output (HTML encoding).

### Authentication
- [ ] Brute force protection is enabled (rate limiting/lockout).
- [ ] Password reset links expire and can only be used once.

### Access Control
- [ ] All API endpoints enforce authorization checks (server-side).
- [ ] IDOR (Insecure Direct Object Reference) checks are in place for all resource access (e.g., `/users/123`).

### Data Protection
- [ ] PII (Personally Identifiable Information) is identified and protected.
- [ ] Sensitive data is masked in logs (e.g., `password`, `credit_card`).

## 4. Rate Limiting & Abuse Prevention
- **Public APIs**: MUST have rate limiting (e.g., 100 requests/min per IP).
- **Auth Endpoints**: Strict rate limits (e.g., 5 attempts/min).

## 5. Security Reviews
- **Constraint**: Any code touching auth, payments, or critical data REQUIRES a focused security review.
- **Trigger**: New dependencies or major architectural changes trigger a security re-assessment.