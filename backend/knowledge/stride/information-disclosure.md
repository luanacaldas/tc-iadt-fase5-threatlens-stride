# Information Disclosure — STRIDE Category Reference

## Definition

Information disclosure occurs when data is exposed to unauthorized parties, whether intentionally or through system misconfiguration. It targets the **confidentiality** dimension of security.

## Common Patterns in Software Architecture

### Data at Rest Exposure

- Unencrypted database records containing PII, credentials, or financial data
- Public cloud storage buckets accessible without authentication
- Backup files stored without encryption in shared storage
- Secrets or API keys committed to source code repositories
- Excessive data retention exposing historical sensitive records

### Data in Transit Exposure

- HTTP (unencrypted) connections between services
- Weak TLS configurations allowing downgrade attacks
- Internal service calls without transport encryption
- Log files transmitted unencrypted to external services

### Excessive Data Exposure

- API responses returning full database records when only a subset is needed
- Error messages exposing stack traces, internal paths, library versions, or query details
- Verbose logging capturing request bodies containing sensitive parameters
- Debug endpoints left enabled in production

### Indicators of Information Disclosure Risk in Architecture

- Database with sensitive data and no encryption component (KMS/secrets manager)
- API responses without field filtering
- Internal flows over HTTP rather than HTTPS
- Storage component without access controls

## Countermeasures by Component

- **Database**: AES-256 at rest, column-level encryption for PII, parameterized queries
- **Storage**: Block public access, SSE-KMS, pre-signed URLs with short expiry
- **Secrets/KMS**: Least-privilege decrypt, audit all key usage, automatic rotation
- **API Gateway**: Response schema filtering, opaque error responses, no version disclosure
- **Monitoring**: Log redaction for tokens and PII, access-controlled log store

## OWASP and Standards References

- OWASP A02:2021 Cryptographic Failures
- OWASP A03:2021 Injection (SQL injection → data exposure)
- CWE-200: Exposure of Sensitive Information to an Unauthorized Actor
- CWE-312: Cleartext Storage of Sensitive Information
- CWE-319: Cleartext Transmission of Sensitive Information
- NIST SP 800-111: Guide to Storage Encryption Technologies
- PCI DSS Requirement 3 & 4: Protect stored and transmitted cardholder data
