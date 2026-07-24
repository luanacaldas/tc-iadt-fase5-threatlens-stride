# API Gateway — Threats and Security Controls

## Component Overview

An API Gateway is the single entry point for all client requests to backend microservices. It handles authentication, authorization, rate limiting, request routing, schema validation, and protocol transformation. Because it sits at the edge of the internal network, it is a high-value target for attackers.

## STRIDE Threat Analysis

### Spoofing — Authentication Bypass

**Risk:** High | **CWE-287** | **OWASP API2:2023 Broken Authentication**

Attack patterns:

- JWT algorithm confusion (alg:none, RS256→HS256 downgrade attacks)
- Bearer token theft via XSS, SSRF, or network interception
- OAuth2 authorization code interception without PKCE
- API key leakage in logs, source code, or error messages
- Replayed tokens after logout

Controls:

- Validate JWT header `alg` field — reject `none` and unexpected algorithms
- Verify `iss`, `aud`, `exp`, `nbf`, and cryptographic signature on every request
- Use short-lived access tokens (≤15 min) with refresh token rotation
- Implement OAuth2 PKCE for public clients
- Apply mTLS for high-trust service-to-service communication
- Rotate signing keys periodically and support key revocation

### Tampering — Request Manipulation

**Risk:** High | **CWE-20, CWE-113** | **OWASP API3:2023 Broken Object Property Level Authorization**

Attack patterns:

- HTTP header injection (Host, X-Forwarded-For, X-Original-URL manipulation)
- Mass assignment (injecting undeclared fields to bypass validation)
- Path traversal via URL routing ambiguity
- Content-type confusion to bypass validation logic

Controls:

- Enforce strict JSON schema validation with allowlisted fields at the gateway
- Normalize and validate all URL paths, headers, and query parameters
- Set explicit Content-Type requirements per endpoint
- Strip or reject unexpected headers before forwarding to backends

### Denial of Service — API Exhaustion

**Risk:** High | **CWE-400** | **OWASP API4:2023 Unrestricted Resource Consumption**

Attack patterns:

- Volumetric DDoS (millions of requests per second)
- Slow HTTP attacks holding connections open
- Expensive query attacks targeting backend computation
- Credential stuffing campaigns against authentication endpoints

Controls:

- Implement tiered rate limiting: per IP, per authenticated user, per API key
- Set connection timeouts, maximum request body size, and response size limits
- Use circuit breakers to prevent cascading backend failures
- Monitor request volume, error rates, and latency with automated alerting

### Information Disclosure — Response Data Leakage

**Risk:** Medium | **CWE-200** | **OWASP API3:2023**

Controls:

- Apply response schema filtering — allowlist fields returned per endpoint
- Return consistent, opaque error messages (no stack traces, internal paths, or versions)
- Disable debug and diagnostic endpoints in production environments
- Suppress version disclosure in response headers

## Security References

- OWASP API Security Top 10: https://owasp.org/API-Security/
- CWE-287: Improper Authentication
- NIST SP 800-204: Security Strategies for Microservices
