# Tampering — STRIDE Category Reference

## Definition

Tampering involves the unauthorized modification of data, code, or configuration. It targets the **integrity** dimension of security.

## Common Patterns in Software Architecture

### Data Tampering

- SQL injection enabling unauthorized UPDATE or DELETE operations
- Man-in-the-middle modification of data in transit
- Message queue payload modification before consumer processing
- Database record modification by overprivileged application accounts
- File upload replacing legitimate assets with malicious files

### Code and Configuration Tampering

- Unauthorized deployment of modified application code
- Container image replacement with malicious version in registry
- Environment variable injection during deployment pipeline
- CI/CD pipeline compromise to inject backdoors into build artifacts
- Infrastructure-as-code modification to introduce misconfigurations

### Indicators of Tampering Risk in Architecture

- Data flows without TLS or transport integrity protection
- Compute-to-database flows with write access where read-only would suffice
- No code signing or artifact integrity validation shown
- Missing WAF upstream of public APIs
- Queue consumers that don't validate message signatures

## Countermeasures by Component

- **API Gateway**: Request schema validation, header normalization, reject unexpected fields
- **Database**: Parameterized queries, audit trails, row-level security, change data capture
- **Compute**: Signed deployments, immutable artifacts, dependency scanning
- **Storage**: Object versioning, MFA delete, write-once retention
- **Queue**: Message signing, idempotency keys, replay protection

## OWASP and Standards References

- OWASP A03:2021 Injection
- OWASP A08:2021 Software and Data Integrity Failures
- CWE-89: SQL Injection
- CWE-20: Improper Input Validation
- CWE-494: Download of Code Without Integrity Check
- NIST SP 800-161: Cybersecurity Supply Chain Risk Management
