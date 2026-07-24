# Identity Provider — Threats and Security Controls

## Component Overview

An Identity Provider (IdP) is the authoritative source of user identity and authentication tokens. It issues JWTs, SAML assertions, or OAuth2 tokens trusted by all relying parties in the architecture. Compromising the IdP gives an attacker access to every dependent service.

## STRIDE Threat Analysis

### Spoofing — Identity Provider Compromise

**Risk:** Critical | **CWE-287, CWE-290** | **OWASP A07:2021 Identification and Authentication Failures**

Attack patterns:

- Phishing or credential stuffing against IdP admin accounts
- SAML response forgery (XML signature wrapping attacks)
- JWT signing key theft enabling forged token generation
- OAuth2 authorization server misconfiguration (open redirect, token leakage)
- Session hijacking after successful authentication

Controls:

- Enforce MFA for all accounts, especially administrative users
- Implement conditional access policies (device trust, location, risk score)
- Protect signing keys with HSM or cloud KMS — never store in application config
- Monitor for anomalous sign-in patterns (impossible travel, new device, failed attempts)
- Apply account lockout after failed authentication attempts with progressive delays
- Implement token binding to prevent token theft across sessions

### Elevation of Privilege — Role Abuse

**Risk:** High | **CWE-269** | **OWASP A01:2021 Broken Access Control**

Attack patterns:

- Overprivileged roles assigned during development never revoked
- Direct object reference in user claims allowing privilege escalation
- Group membership manipulation via self-service portal
- Token claims manipulation if validation is weak at relying parties

Controls:

- Review all role and group assignments quarterly with a formal access review process
- Implement just-in-time (JIT) access with time-limited approvals for privileged operations
- Apply separation of duties — no single account can both administer the IdP and use it
- Validate all claims at every relying party — do not trust IdP-issued tokens without re-validation
- Use attribute-based access control (ABAC) for fine-grained authorization

## Security References

- OWASP Authentication Cheat Sheet
- NIST SP 800-63B: Digital Identity Guidelines
- OAuth 2.0 Security Best Current Practice (RFC 9700)
- CWE-287: Improper Authentication
