# Secrets Manager / KMS — Threats and Security Controls

## Component Overview

A Secrets Manager or Key Management Service (KMS) stores and manages sensitive credentials: API keys, database passwords, TLS certificates, and cryptographic keys. Unauthorized access to this component exposes all secrets stored within it, potentially compromising the entire architecture.

## STRIDE Threat Analysis

### Information Disclosure — Secret Exfiltration

**Risk:** Critical | **CWE-200, CWE-321** | **OWASP A02:2021 Cryptographic Failures**

Attack patterns:

- Overprivileged IAM roles with broad decrypt permissions
- Application code logging secret values accidentally
- Secrets stored in environment variables exposed via process listing
- Backup snapshots of secrets vaults without proper access control
- Insecure secret transmission over unencrypted channels

Controls:

- Apply least-privilege access: each service can only access the specific secrets it needs
- Use envelope encryption — data keys wrapped by a master key that never leaves the KMS
- Enable audit logging for every secret access, rotation, and administrative action
- Alert on abnormal decryption volume (e.g., 10x normal access rate)
- Rotate all secrets automatically on a defined schedule (passwords: 90 days, API keys: 180 days)
- Never log, print, or store raw secret values in application logs

### Elevation of Privilege — Key Policy Abuse

**Risk:** High | **CWE-269**

Attack patterns:

- Overly permissive KMS key policies granting decrypt to all principals
- Key administrators who can also use the keys (no separation of duties)
- Cross-account key sharing without proper trust policies
- Key deletion or disabling as a sabotage vector

Controls:

- Separate key administrator role from key user role — no single identity should have both
- Require MFA for all key administrative operations (create, delete, rotate, modify policy)
- Set key deletion windows (minimum 7 days) with notification and approval workflows
- Restrict cross-account key usage to explicitly allowlisted accounts
- Use dedicated KMS keys per application/environment — avoid sharing keys across trust boundaries

## Security References

- NIST SP 800-57: Recommendation for Key Management
- CWE-321: Use of Hard-coded Cryptographic Key
- OWASP Secrets Management Cheat Sheet
- AWS KMS Best Practices / Azure Key Vault security guide
