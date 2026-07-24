# End User — Threats and Security Controls

## Component Overview

The end user is an external actor interacting with the system through a client application (browser, mobile app, or API client). Users are the most frequent attack vector and also frequent targets of phishing, account takeover, and social engineering.

## STRIDE Threat Analysis

### Spoofing — Account Takeover

**Risk:** Medium | **CWE-287** | **OWASP A07:2021 Identification and Authentication Failures**

Attack patterns:

- Credential stuffing using leaked username/password combinations from other breaches
- Phishing attacks stealing session tokens or credentials
- Session hijacking via XSS or network interception
- Brute force attacks against weak passwords

Controls:

- Require strong passwords with minimum entropy; support passkeys
- Enforce MFA for all accounts, especially those with access to sensitive data
- Use secure, HttpOnly, SameSite=Strict cookie attributes for session tokens
- Implement short session lifetimes with sliding expiration for sensitive applications
- Bind re-authentication to high-risk actions (payment, password change, account settings)
- Deploy account lockout with progressive delays and CAPTCHA after failed attempts

### Repudiation — Unattributable Actions

**Risk:** Medium | **CWE-778**

Attack patterns:

- User denying actions when no reliable audit trail exists
- Shared accounts making individual attribution impossible
- Missing event logs for critical user actions (data export, deletion, configuration changes)

Controls:

- Enforce one account per person — prohibit shared accounts
- Log all security-relevant user actions with: user ID, session ID, IP, timestamp, action, and affected resource
- Use non-repudiation mechanisms (digital signatures) for legally binding actions
- Protect audit logs: users must not be able to delete or modify their own audit records

## Security References

- OWASP Authentication Cheat Sheet
- NIST SP 800-63B: Authentication and Lifecycle Management
- CWE-287: Improper Authentication
