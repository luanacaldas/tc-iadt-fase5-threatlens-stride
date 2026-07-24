# Load Balancer — Threats and Security Controls

## Component Overview

A load balancer distributes incoming traffic across multiple backend instances for availability and performance. It can terminate TLS, perform health checks, and route based on content. Misconfiguration can route traffic to malicious backends or create a single point of failure.

## STRIDE Threat Analysis

### Tampering — Traffic Routing Manipulation

**Risk:** Medium | **CWE-923**

Attack patterns:

- Unauthorized modification of backend pool to add malicious endpoint
- SSL certificate substitution on TLS-terminating load balancers
- Sticky session abuse routing all traffic to one backend
- Health check manipulation to remove legitimate backends from rotation

Controls:

- Restrict load balancer administration to privileged IAM roles with MFA
- Use change management workflows for all backend pool and listener modifications
- Monitor health check results and alert on unexpected backend removals
- Validate TLS certificates on backends when the LB forwards traffic (end-to-end TLS)

### Denial of Service — Bottleneck Exhaustion

**Risk:** High | **CWE-400**

Controls:

- Enable connection rate limiting and maximum concurrent connections per client IP
- Integrate with cloud DDoS protection upstream of the load balancer
- Configure autoscaling to expand backend capacity under load
- Monitor saturation metrics: active connections, requests per second, and dropped connections

## Security References

- CWE-923: Improper Restriction of Communication Channel
- NIST SP 800-44: Guidelines on Securing Public Web Servers
