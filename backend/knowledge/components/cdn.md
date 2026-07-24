# CDN (Content Delivery Network) — Threats and Security Controls

## Component Overview

A CDN caches and distributes static and dynamic content at edge nodes close to end users. It reduces origin load and improves performance. Misconfigured caching can expose private responses; weak origin protection allows CDN bypass.

## STRIDE Threat Analysis

### Information Disclosure — Cache Poisoning and Private Content Exposure

**Risk:** Medium | **CWE-200, CWE-444**

Attack patterns:

- CDN caching authenticated or personalized responses and serving them to other users
- Cache key manipulation (Host header injection, X-Forwarded-Host) to poison shared cache
- CDN edge serving stale responses after content update (cache invalidation lag)
- Direct origin access bypassing CDN security controls

Controls:

- Set `Cache-Control: no-store, private` on all authenticated or user-specific responses
- Validate and normalize cache key headers at the CDN edge
- Restrict origin access to CDN IP ranges only — block direct-to-origin requests
- Implement cache purge workflows triggered on sensitive content updates
- Use signed cookies or signed URLs to protect content delivery for authorized users

### Tampering — Origin Bypass and Cache Injection

**Risk:** Medium | **CWE-345**

Controls:

- Force all traffic through the CDN — do not expose origin directly on public IP
- Use CDN-to-origin authentication (shared secret header or mTLS)
- Serve static assets with Subresource Integrity (SRI) hashes in HTML
- Monitor for CDN configuration changes with automated change detection

## Security References

- OWASP Web Cache Deception Attack
- CWE-200: Exposure of Sensitive Information to an Unauthorized Actor
- RFC 9111: HTTP Caching
