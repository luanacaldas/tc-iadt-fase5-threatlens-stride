# Denial of Service — STRIDE Category Reference

## Definition

Denial of Service (DoS) involves making a system unavailable to legitimate users by exhausting resources, overwhelming capacity, or triggering crashes. Distributed versions (DDoS) amplify the impact. It targets the **availability** dimension of security.

## Common Patterns in Software Architecture

### Volumetric Attacks

- UDP/ICMP floods saturating network bandwidth
- SYN floods exhausting TCP connection state tables
- Amplification attacks (DNS, NTP, memcached reflection)
- HTTP floods from botnets overwhelming web servers

### Resource Exhaustion

- Memory leak or CPU-intensive operation triggered by crafted input
- Database connection pool exhaustion via slow queries
- Disk exhaustion via unbounded log growth or file upload without size limits
- Thread pool exhaustion via high-latency downstream dependencies (cascading failure)

### Application-Layer Attacks

- Regex Denial of Service (ReDoS) via malicious input matching catastrophic backtracking patterns
- Expensive GraphQL or REST queries without complexity limits
- Credential stuffing campaigns generating authentication load
- Queue flooding by malicious message producers

### Indicators of DoS Risk in Architecture

- No WAF or rate limiting component upstream of public APIs
- Database without connection pooling or query timeout configuration
- Queue without dead-letter queue or consumer rate limits
- No autoscaling or load balancing between internet and compute
- Missing backup component for database (recovery failure under DoS)

## Countermeasures by Component

- **WAF**: Rate limiting, bot control, request size limits, connection throttling
- **API Gateway**: Throttling quotas per consumer, circuit breakers, request body size limit
- **Load Balancer**: Connection limits, health checks, autoscaling triggers
- **Database**: Query timeouts, connection pooling, read replicas, resource quotas
- **Queue**: Producer rate limits, max message size, dead-letter queue, consumer backpressure

## OWASP and Standards References

- OWASP A04:2021 Insecure Design (resource exhaustion patterns)
- OWASP API4:2023 Unrestricted Resource Consumption
- CWE-400: Uncontrolled Resource Consumption
- CWE-770: Allocation of Resources Without Limits or Throttling
- NIST SP 800-61: Computer Security Incident Handling Guide
