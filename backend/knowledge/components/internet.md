# Internet / Public Network — Threats and Security Controls

## Component Overview

The Internet represents the untrusted external network through which all public user traffic flows. Any component directly reachable from the Internet is exposed to the full range of automated attacks, botnets, and human adversaries.

## STRIDE Threat Analysis

### Denial of Service — Volumetric and Application-Layer Attacks

**Risk:** High | **CWE-400**

Attack patterns:

- Layer 3/4 DDoS (UDP floods, SYN floods)
- Layer 7 application-layer attacks (HTTP floods, Slowloris)
- Amplification attacks using DNS, NTP, memcached reflection
- Botnet-driven credential stuffing and brute force

Controls:

- Integrate cloud-native DDoS protection (AWS Shield Advanced, Azure DDoS Standard)
- Place all public traffic behind a WAF and CDN for edge filtering
- Implement anycast IP routing to absorb volumetric attacks at the edge
- Establish incident response playbook for DDoS with automated traffic scrubbing
- Define abuse rate thresholds and automated blocking for offending IP ranges

### Tampering — Network Transport Weakness

**Risk:** High | **CWE-319**

Attack patterns:

- Man-in-the-middle interception on networks without TLS
- TLS downgrade attacks (POODLE, BEAST, DROWN on weak cipher suites)
- DNS hijacking redirecting users to malicious endpoints
- BGP hijacking rerouting traffic through adversarial networks

Controls:

- Enforce TLS 1.2 minimum, prefer TLS 1.3 for all public endpoints
- Use HSTS with long max-age and includeSubDomains; submit to HSTS preload list
- Enable DNSSEC to authenticate DNS responses
- Monitor BGP routing announcements for unexpected prefix hijacking
- Disable all weak cipher suites (RC4, DES, 3DES, export-grade)

## Security References

- CWE-319: Cleartext Transmission of Sensitive Information
- OWASP Transport Layer Security Cheat Sheet
- NIST SP 800-52: Guidelines for TLS Implementations
