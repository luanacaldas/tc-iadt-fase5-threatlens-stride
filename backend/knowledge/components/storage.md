# Storage (Object/Blob Storage) — Threats and Security Controls

## Component Overview

Object storage (S3, Azure Blob, GCS) holds files, backups, static assets, ML models, and exported data. Misconfigured storage is one of the most frequent causes of large-scale data breaches (e.g., public S3 buckets exposing millions of records).

## STRIDE Threat Analysis

### Information Disclosure — Public Bucket Exposure

**Risk:** High | **CWE-200, CWE-284**

Attack patterns:

- Storage bucket configured with public read access (ACL misconfiguration)
- Signed URLs with excessively long expiry times shared insecurely
- Object metadata leaking internal path structure or user data
- Bucket enumeration through predictable naming conventions

Controls:

- Block all public access at the account/organization level by default
- Audit bucket and container policies weekly using cloud security posture management (CSPM)
- Encrypt all objects with SSE-KMS (server-side encryption with customer-managed keys)
- Use pre-signed URLs with short expiry (< 1 hour) for temporary access
- Apply bucket access logging and alert on direct public reads to private buckets
- Run data classification scans to identify objects containing PII or sensitive data

### Tampering — Object Integrity Violation

**Risk:** Medium | **CWE-345**

Attack patterns:

- Malicious file upload replacing legitimate assets (supply chain attack vector)
- Object version deletion removing audit evidence
- Lifecycle policy misconfiguration causing premature deletion

Controls:

- Enable object versioning to maintain history and support rollback
- Enable MFA delete for critical buckets to require multi-factor confirmation for permanent deletion
- Use object lock with WORM retention for compliance and evidence preservation
- Validate file content (MIME type, size, malware scan) before storing user-uploaded objects
- Apply separate IAM roles for read vs. write access

## Security References

- CWE-200: Exposure of Sensitive Information
- OWASP Cloud Security Top 10
- AWS S3 Security Best Practices / Azure Blob Storage security guide
