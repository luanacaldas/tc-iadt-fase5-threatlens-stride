# Spoofing — STRIDE Category Reference

## Definition

Spoofing is the act of impersonating another user, process, or system to gain unauthorized access or trust. It targets the **authentication** dimension of security.

## Common Patterns in Software Architecture

### Identity Spoofing

- Forged JWT tokens (algorithm confusion, signature bypass, expired token reuse)
- API key theft and reuse across different clients or IP ranges
- Session token theft via XSS, CSRF, or network interception
- Credential stuffing using leaked username/password databases
- OAuth2 authorization code theft without PKCE protection

### Service Spoofing

- DNS hijacking redirecting service calls to malicious endpoints
- Man-in-the-middle via TLS downgrade or certificate substitution
- Spoofed microservice calling internal APIs without proper authentication
- IP spoofing to bypass IP allowlists

### Indicators of Spoofing Risk in Architecture

- Authentication not shown at public entry points (Internet → API)
- No identity provider in the architecture
- Direct user-to-database flows without intermediate authentication layer
- HTTP (non-HTTPS) protocols on public flows
- Absence of trust boundary indicators between external and internal zones

## Countermeasures by Component

- **API Gateway**: Validate JWT (iss, aud, exp, alg); enforce OAuth2/OIDC; mTLS for services
- **Identity Provider**: MFA, conditional access, signing key rotation, anomalous login detection
- **User**: MFA, account lockout, re-authentication for sensitive actions
- **Load Balancer**: Mutual TLS between clients and backend

## OWASP and Standards References

- OWASP A07:2021 Identification and Authentication Failures
- OWASP Authentication Cheat Sheet
- NIST SP 800-63B: Digital Identity Guidelines
- RFC 9700: OAuth 2.0 Security Best Current Practice
- CWE-287: Improper Authentication
- CWE-290: Authentication Bypass by Spoofing
- CWE-345: Insufficient Verification of Data Authenticity
