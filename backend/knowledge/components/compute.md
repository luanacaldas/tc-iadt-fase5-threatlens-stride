# Compute / Application Server — Threats and Security Controls

## Component Overview

The compute layer runs the application business logic — containers, virtual machines, serverless functions, or microservices. It processes user requests, integrates with databases, queues, and external APIs. Compromise of a compute workload can enable lateral movement to all connected systems.

## STRIDE Threat Analysis

### Elevation of Privilege — Workload Compromise

**Risk:** High | **CWE-269, CWE-250** | **OWASP A01:2021 Broken Access Control**

Attack patterns:

- Instance Metadata Service (IMDS) exploitation to steal IAM credentials (SSRF → IMDS)
- Container escape from compromised pod to host node
- Overprivileged service accounts with write access to production resources
- Dependency chain attacks (compromised npm/pip package with embedded backdoor)
- Long-lived credentials embedded in deployment artifacts

Controls:

- Use IMDSv2 (session-oriented) on AWS EC2; disable IMDS access for containers that don't need it
- Assign dedicated service accounts with least-privilege IAM roles scoped to the minimum needed
- Avoid long-lived static credentials — use workload identity federation or instance profiles
- Run containers as non-root with read-only filesystems where possible
- Scan all dependencies for known vulnerabilities (CVE) in CI/CD pipelines
- Enforce network policies to limit egress from compute workloads

### Tampering — Code and Configuration Integrity

**Risk:** High | **CWE-494** | **OWASP A08:2021 Software and Data Integrity Failures**

Attack patterns:

- Unauthorized deployment of modified application code
- Environment variable injection during deployment
- Malicious base image in container registry
- CI/CD pipeline compromise to inject malicious code

Controls:

- Sign container images and verify signatures at deployment time
- Use immutable infrastructure — no SSH or runtime modifications to production instances
- Enforce code review and approval gates in CI/CD pipelines
- Scan base images for vulnerabilities; use minimal distroless images
- Separate deployment credentials from runtime credentials

### Repudiation — Missing Action Attribution

**Risk:** Medium | **CWE-778**

Controls:

- Propagate request correlation IDs (X-Request-ID, X-Trace-ID) across all service calls
- Log: actor identity, service identity, request ID, action, authorization decision, and timestamp
- Ship logs to an immutable, centralized log store that the application cannot modify

## Security References

- OWASP Top 10 A08:2021 Software and Data Integrity
- CWE-269: Improper Privilege Management
- NIST SP 800-190: Application Container Security Guide
