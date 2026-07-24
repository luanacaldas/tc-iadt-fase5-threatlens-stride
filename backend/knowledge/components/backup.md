# Backup — Threats and Security Controls

## Component Overview

Backup systems protect against data loss from ransomware, accidental deletion, and disaster scenarios. They are also a target for attackers who seek to destroy recovery capability before deploying destructive payloads (ransomware pre-attack pattern).

## STRIDE Threat Analysis

### Tampering — Backup Destruction (Ransomware Pre-attack)

**Risk:** High | **CWE-284**

Attack patterns:

- Ransomware deleting or encrypting backups before encrypting primary data
- Insider threat deleting backups to enable extortion
- Misconfigured retention policy causing automatic backup deletion
- Cloud snapshot sharing with unauthorized accounts

Controls:

- Use immutable backups with write-once-read-many (WORM) storage
- Store backups in a separate account, subscription, or region from primary data
- Apply separation of duties: the backup admin role cannot delete backups; requires a second approval
- Enable backup vault lock (AWS Backup Vault Lock / Azure Backup immutability)
- Test backup restoration monthly — document and enforce RTO/RPO targets

### Denial of Service — Recovery Failure During Incident

**Risk:** High | **CWE-400**

Attack patterns:

- Untested backups that cannot be successfully restored
- Backup jobs silently failing without alerting
- RPO exceeded due to infrequent backups relative to data change rate

Controls:

- Run automated restore tests in a sandbox environment on a scheduled basis
- Alert on any backup job failure within 1 hour of the expected completion time
- Monitor backup coverage: every database and critical storage bucket should have a backup job configured
- Document recovery runbooks and test them during incident drills

## Security References

- NIST SP 800-34: Contingency Planning Guide for Federal Information Systems
- CWE-284: Improper Access Control
