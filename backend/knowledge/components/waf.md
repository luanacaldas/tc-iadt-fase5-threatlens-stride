# WAF (Web Application Firewall) — Threats and Security Controls

## Component Overview

A WAF inspects HTTP/HTTPS traffic for malicious patterns before it reaches the application. It blocks SQL injection, XSS, CSRF, protocol anomalies, bot traffic, and known exploit signatures. A misconfigured or missing WAF leaves the entire public surface unprotected.

## STRIDE Threat Analysis

### Tampering — WAF Rule Bypass

**Risk:** Medium | **CWE-20**

Attack patterns:

- Encoding tricks (double URL encoding, null bytes, Unicode normalization) to bypass rule patterns
- HTTP parameter pollution to confuse WAF inspection
- Fragmented payloads spread across multiple requests
- Out-of-band injection (DNS, HTTP callbacks) that WAF cannot inspect
- Relying on managed rules that lag behind new CVEs

Controls:

- Enable AWS Managed Rules / Azure Managed Rule Sets as baseline; customize per application
- Enable anomaly scoring mode (not block mode for new rules) during initial rollout
- Review WAF logs weekly for false positives and tuning opportunities
- Test WAF rules with a controlled penetration test before and after rule changes
- Use positive security model (allowlisting expected patterns) for critical endpoints

### Denial of Service — WAF Saturation

**Risk:** Medium | **CWE-400**

Attack patterns:

- Overwhelming WAF capacity before rules can engage
- Exploiting WAF latency to mount slow attacks that bypass thresholds
- Targeting WAF rule evaluation overhead with complex payloads

Controls:

- Combine WAF with cloud-native DDoS protection (AWS Shield, Azure DDoS Protection)
- Set request rate limits at the WAF level as a first line of defense
- Monitor WAF throughput, blocked request rate, and latency added by inspection
- Enable bot control to separate legitimate traffic from automated attacks

## Security References

- OWASP Web Application Firewall Evaluation Criteria Project
- CWE-20: Improper Input Validation
- NIST SP 800-44: Guidelines on Securing Public Web Servers
