# Monitoring and Logging — Threats and Security Controls

## Component Overview

Centralized monitoring and logging provides observability, auditability, and incident detection capability. Without it, attacks can go undetected for months (average attacker dwell time: 197 days). Logs are also primary forensic evidence.

## STRIDE Threat Analysis

### Repudiation — Missing or Incomplete Audit Trail

**Risk:** High | **CWE-778** | **OWASP A09:2021 Security Logging and Monitoring Failures**

Attack patterns:

- Attacker disables logging before executing attack to avoid detection
- Log shipping failure due to misconfigured agents
- Log truncation or rotation deleting evidence before investigation
- Missing correlation IDs making event reconstruction impossible

Controls:

- Centralize all logs to an immutable log store with WORM (Write Once Read Many) retention
- Log these events at minimum: authentication (success + failure), authorization decisions, data access, privilege changes, administrative actions, and errors
- Include: timestamp (UTC), actor identity, source IP, request ID, action, resource, and outcome
- Set log retention: 90 days hot, 1 year cold (or per regulatory requirement)
- Alert on log agent failures, missing heartbeats, or sudden drop in log volume
- Ship logs to a separate account/subscription with restricted access

### Information Disclosure — Log Data Exposure

**Risk:** Medium | **CWE-532**

Attack patterns:

- Sensitive data logged by application (tokens, passwords, PII, credit card numbers)
- Log access granted to overly broad roles
- Logs forwarded to third-party services without masking

Controls:

- Implement log scrubbing middleware to redact tokens, passwords, and PII before writing
- Apply log access control: only security/SRE teams have raw log access; application teams have filtered views
- Scan log pipelines regularly for accidental sensitive data inclusion
- Review third-party log forwarding configurations for data residency and privacy compliance

## Security References

- OWASP Logging Cheat Sheet
- CWE-532: Insertion of Sensitive Information into Log File
- NIST SP 800-92: Guide to Computer Security Log Management
