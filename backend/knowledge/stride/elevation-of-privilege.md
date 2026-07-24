# Elevation of Privilege — STRIDE Category Reference

## Definition

Elevation of Privilege occurs when a user or process gains access rights beyond what they are authorized for, enabling actions they should not be able to perform. It targets the **authorization** dimension of security.

## Common Patterns in Software Architecture

### Horizontal Privilege Escalation

- Accessing another user's data by manipulating object identifiers (IDOR)
- Broken access control in multi-tenant applications sharing the same database
- JWT claims manipulation to switch user roles or tenant context

### Vertical Privilege Escalation

- Exploiting IAM misconfiguration to assume higher-privileged cloud roles
- SSRF to metadata service (IMDS) to steal EC2/VM instance credentials
- Container escape from compromised pod to host node with root access
- Dependency vulnerability granting RCE with server-level privileges
- Overprivileged database accounts enabling DDL operations from application code

### Privilege Persistence

- Backdoor accounts created during initial compromise
- SSH keys added to authorized_keys on compute instances
- Scheduled tasks or cron jobs planted for persistent access
- Service accounts with non-expiring credentials

### Indicators of Elevation of Privilege Risk in Architecture

- Compute workloads with broad IAM permissions (AdministratorAccess, Owner)
- No secrets manager shown (implies hardcoded or broadly shared credentials)
- Identity provider without MFA or conditional access
- Internal service-to-service calls without authentication
- Missing network segmentation between trust zones

## Countermeasures by Component

- **Compute**: Least-privilege IAM roles, IMDSv2, no hardcoded credentials, workload identity
- **Identity Provider**: MFA, conditional access, JIT privilege elevation, quarterly access review
- **Secrets/KMS**: Separate key admin from key user roles, MFA for admin operations
- **API Gateway**: Validate JWT claims, enforce scope-based access per endpoint, RBAC
- **Database**: Application-specific roles, no shared DBA credentials, row-level security

## OWASP and Standards References

- OWASP A01:2021 Broken Access Control
- OWASP A04:2021 Insecure Design
- CWE-269: Improper Privilege Management
- CWE-250: Execution with Unnecessary Privileges
- CWE-639: Authorization Bypass Through User-Controlled Key (IDOR)
- NIST SP 800-53 AC-6: Least Privilege
