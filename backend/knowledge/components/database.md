# Database — Threats and Security Controls

## Component Overview

Databases store the most sensitive data in an architecture: user PII, financial records, credentials, session tokens, and business-critical information. A database breach typically constitutes the highest-severity security event in any system.

## STRIDE Threat Analysis

### Information Disclosure — Data Breach

**Risk:** Critical | **CWE-200, CWE-312** | **OWASP A02:2021 Cryptographic Failures**

Attack patterns:

- SQL injection granting direct table access
- Overprivileged application accounts with SELECT on all tables
- Unencrypted data at rest exposed through storage-layer access
- Database credentials hardcoded in application code or config files
- Backup files stored unencrypted and publicly accessible

Controls:

- Encrypt all data at rest using AES-256 or cloud KMS-managed keys
- Apply column-level encryption for PII, financial data, and credentials
- Use parameterized queries or ORMs — never concatenate user input into queries
- Assign least-privilege database roles per service (SELECT only where writes are not needed)
- Tokenize or mask sensitive fields (card numbers, SSNs) before storage

### Tampering — Unauthorized Data Modification

**Risk:** High | **CWE-89, CWE-284**

Attack patterns:

- SQL injection enabling UPDATE or DELETE statements
- Insider threats with direct database access
- Application bugs bypassing authorization before database writes
- Missing audit trail allowing undetected modifications

Controls:

- Use database-level row-level security for multi-tenant data isolation
- Enable audit logging for all INSERT, UPDATE, DELETE operations on sensitive tables
- Implement soft-delete patterns to retain history for forensic analysis
- Set up change data capture (CDC) for critical tables
- Monitor for abnormal write volumes and privilege escalation via database activity monitoring

### Denial of Service — Resource Exhaustion

**Risk:** High | **CWE-400**

Attack patterns:

- Unbounded queries consuming full table scans (missing indexes)
- Connection pool exhaustion through slow queries
- Storage exhaustion via uncontrolled data ingestion
- Lock contention attacks through intentional long-running transactions

Controls:

- Set query timeouts at both the application and database level
- Implement connection pooling with maximum connection limits per service
- Use read replicas to offload reporting queries from the primary
- Alert on CPU > 80%, storage > 75%, active connections > threshold, and lock wait events
- Add pagination to all list endpoints to prevent unbounded result sets

## Security References

- OWASP SQL Injection Prevention Cheat Sheet
- CWE-89: SQL Injection
- NIST SP 800-111: Guide to Storage Encryption Technologies
- PCI DSS Requirement 3: Protect stored cardholder data
