# Repudiation — STRIDE Category Reference

## Definition

Repudiation occurs when a user or process can deny having performed an action because there is no reliable, tamper-proof audit trail. It targets the **non-repudiation** dimension of security.

## Common Patterns in Software Architecture

### Missing Audit Trails

- No centralized logging component in the architecture
- Application logs stored locally on compute instances that can be deleted
- Critical actions (data deletion, privilege changes, exports) not logged
- Shared accounts making individual attribution impossible

### Mutable or Incomplete Logs

- Logs stored in writable locations accessible to the application
- Log rotation deleting evidence before investigation window
- Missing correlation IDs making end-to-end request reconstruction impossible
- Inconsistent log formats preventing effective querying

### Indicators of Repudiation Risk in Architecture

- No monitoring or logging component visible in the diagram
- Compute components without outbound connections to a logging service
- Database write operations with no audit trail component
- External integrations without request/response logging

## Countermeasures by Component

- **Monitoring**: Immutable log store, centralized aggregation, WORM retention, access control on logs
- **Compute**: Correlation IDs propagated across all service calls, structured logging
- **API Gateway**: Access logs with full request metadata (IP, user, path, status, latency)
- **Database**: Audit logging on sensitive table operations, change data capture for critical data
- **Identity Provider**: Sign-in audit logs with risk score, MFA events, token issuance

## Mandatory Log Fields

Every security-relevant event should include:

- Timestamp (UTC, ISO 8601)
- Actor identity (user ID, service account)
- Source IP and request correlation ID
- Action and affected resource
- Authorization decision (allow/deny) and policy applied
- Outcome and any error codes

## OWASP and Standards References

- OWASP A09:2021 Security Logging and Monitoring Failures
- OWASP Logging Cheat Sheet
- CWE-778: Insufficient Logging
- CWE-532: Insertion of Sensitive Information into Log File
- NIST SP 800-92: Guide to Computer Security Log Management
