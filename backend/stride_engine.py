"""ThreatLens STRIDE Engine — Python port of src/threatlens.mjs.

Pure Python, zero external dependencies.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

SEVERITY_WEIGHT: dict[str, int] = {
    "Critical": 10,
    "High": 8,
    "Medium": 5,
    "Low": 2,
}

STRIDE_ORDER: list[str] = [
    "Spoofing",
    "Tampering",
    "Repudiation",
    "Information Disclosure",
    "Denial of Service",
    "Elevation of Privilege",
]

THREAT_STATUSES = {"open", "mitigated", "accepted", "false_positive"}

SECURITY_REFERENCES: dict[str, list[dict[str, str]]] = {
    "Spoofing": [
        {"framework": "CWE", "id": "CWE-287", "title": "Improper Authentication", "url": "https://cwe.mitre.org/data/definitions/287.html"},
        {"framework": "CAPEC", "id": "CAPEC-115", "title": "Authentication Bypass", "url": "https://capec.mitre.org/data/definitions/115.html"},
        {"framework": "OWASP", "id": "A07:2021", "title": "Identification and Authentication Failures", "url": "https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/"},
        {"framework": "MITRE ATT&CK", "id": "T1078", "title": "Valid Accounts", "url": "https://attack.mitre.org/techniques/T1078/"},
    ],
    "Tampering": [
        {"framework": "CWE", "id": "CWE-20", "title": "Improper Input Validation", "url": "https://cwe.mitre.org/data/definitions/20.html"},
        {"framework": "CAPEC", "id": "CAPEC-153", "title": "Input Data Manipulation", "url": "https://capec.mitre.org/data/definitions/153.html"},
        {"framework": "OWASP", "id": "A08:2021", "title": "Software and Data Integrity Failures", "url": "https://owasp.org/Top10/A08_2021-Software_and_Data_Integrity_Failures/"},
        {"framework": "MITRE ATT&CK", "id": "T1565", "title": "Data Manipulation", "url": "https://attack.mitre.org/techniques/T1565/"},
    ],
    "Repudiation": [
        {"framework": "CWE", "id": "CWE-778", "title": "Insufficient Logging", "url": "https://cwe.mitre.org/data/definitions/778.html"},
        {"framework": "CAPEC", "id": "CAPEC-268", "title": "Audit Log Manipulation", "url": "https://capec.mitre.org/data/definitions/268.html"},
        {"framework": "OWASP", "id": "A09:2021", "title": "Security Logging and Monitoring Failures", "url": "https://owasp.org/Top10/A09_2021-Security_Logging_and_Monitoring_Failures/"},
        {"framework": "MITRE ATT&CK", "id": "T1070", "title": "Indicator Removal", "url": "https://attack.mitre.org/techniques/T1070/"},
    ],
    "Information Disclosure": [
        {"framework": "CWE", "id": "CWE-200", "title": "Exposure of Sensitive Information", "url": "https://cwe.mitre.org/data/definitions/200.html"},
        {"framework": "CAPEC", "id": "CAPEC-118", "title": "Data Leakage Attacks", "url": "https://capec.mitre.org/data/definitions/118.html"},
        {"framework": "OWASP", "id": "A02:2021", "title": "Cryptographic Failures", "url": "https://owasp.org/Top10/A02_2021-Cryptographic_Failures/"},
        {"framework": "MITRE ATT&CK", "id": "T1530", "title": "Data from Cloud Storage", "url": "https://attack.mitre.org/techniques/T1530/"},
    ],
    "Denial of Service": [
        {"framework": "CWE", "id": "CWE-400", "title": "Uncontrolled Resource Consumption", "url": "https://cwe.mitre.org/data/definitions/400.html"},
        {"framework": "CAPEC", "id": "CAPEC-125", "title": "Resource Depletion through Flooding", "url": "https://capec.mitre.org/data/definitions/125.html"},
        {"framework": "OWASP", "id": "API4:2023", "title": "Unrestricted Resource Consumption", "url": "https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/"},
        {"framework": "MITRE ATT&CK", "id": "T1499", "title": "Endpoint Denial of Service", "url": "https://attack.mitre.org/techniques/T1499/"},
    ],
    "Elevation of Privilege": [
        {"framework": "CWE", "id": "CWE-269", "title": "Improper Privilege Management", "url": "https://cwe.mitre.org/data/definitions/269.html"},
        {"framework": "CAPEC", "id": "CAPEC-233", "title": "Privilege Escalation", "url": "https://capec.mitre.org/data/definitions/233.html"},
        {"framework": "OWASP", "id": "A01:2021", "title": "Broken Access Control", "url": "https://owasp.org/Top10/A01_2021-Broken_Access_Control/"},
        {"framework": "MITRE ATT&CK", "id": "T1068", "title": "Exploitation for Privilege Escalation", "url": "https://attack.mitre.org/techniques/T1068/"},
    ],
}


def _t(stride: str, title: str, severity: str, countermeasures: list[str], confidence: float | None = None) -> dict:
    base: dict[str, Any] = {"stride": stride, "title": title, "severity": severity, "countermeasures": countermeasures}
    if confidence is not None:
        base["confidence"] = confidence
    return base


COMPONENT_KNOWLEDGE: dict[str, dict] = {
    "user": {
        "label": "User",
        "rules": [
            _t("Spoofing", "User identity can be impersonated", "Medium", [
                "Require strong authentication with MFA for privileged flows.",
                "Use short-lived sessions and secure cookie attributes.",
                "Bind sensitive actions to re-authentication.",
            ]),
            _t("Repudiation", "User actions may not be traceable", "Medium", [
                "Log security-relevant actions with user id, source, timestamp, and request correlation id.",
                "Protect audit logs against deletion or tampering.",
            ]),
        ],
    },
    "internet": {
        "label": "Internet",
        "rules": [
            _t("Denial of Service", "Public entry point can be abused by high traffic", "High", [
                "Use rate limiting, WAF rules, bot protection, and autoscaling.",
                "Define abuse thresholds and monitoring alerts for public endpoints.",
            ]),
            _t("Tampering", "Traffic can be altered if transport is weak", "High", [
                "Enforce HTTPS/TLS 1.2+ end to end.",
                "Reject insecure protocols and redirect HTTP to HTTPS.",
            ]),
        ],
    },
    "api_gateway": {
        "label": "API Gateway",
        "rules": [
            _t("Spoofing", "API clients can forge identity or tokens", "High", [
                "Validate JWT issuer, audience, expiration, and signature.",
                "Use OAuth2/OIDC and mTLS for service-to-service integrations.",
                "Apply least privilege scopes per endpoint.",
            ]),
            _t("Tampering", "Request payload can be modified before reaching backend", "High", [
                "Validate schemas at the gateway and backend.",
                "Reject unexpected fields and enforce content-type restrictions.",
            ]),
            _t("Denial of Service", "API endpoint can be overloaded", "High", [
                "Enable throttling, quotas, circuit breakers, and request size limits.",
                "Add alerts for latency spikes and unusual request volume.",
            ]),
            _t("Information Disclosure", "API responses can expose sensitive data", "Medium", [
                "Filter sensitive fields before response serialization.",
                "Use consistent error handling that does not leak stack traces or secrets.",
            ]),
        ],
    },
    "load_balancer": {
        "label": "Load Balancer",
        "rules": [
            _t("Tampering", "Traffic routing can be manipulated", "Medium", [
                "Restrict administration to trusted identities.",
                "Use health checks and signed configuration change workflows.",
            ]),
            _t("Denial of Service", "Load balancer can become a shared bottleneck", "High", [
                "Enable autoscaling, connection limits, and DDoS protection.",
                "Monitor saturation, failed health checks, and dropped connections.",
            ]),
        ],
    },
    "waf": {
        "label": "WAF",
        "rules": [
            _t("Tampering", "Weak WAF policy can allow malicious payloads", "Medium", [
                "Enable managed rules for injection, XSS, protocol anomalies, and known bad IPs.",
                "Review false positives and tune rules with change control.",
            ]),
            _t("Denial of Service", "WAF bypass or weak rate policy can allow abuse", "Medium", [
                "Combine WAF with rate limiting, bot mitigation, and DDoS protection.",
                "Alert on blocked requests and sudden rule hit changes.",
            ]),
        ],
    },
    "compute": {
        "label": "Compute/Server",
        "rules": [
            _t("Elevation of Privilege", "Compromised workload can gain broader permissions", "High", [
                "Use least privilege IAM roles and avoid long-lived credentials.",
                "Harden runtime, patch dependencies, and isolate workloads by trust level.",
            ]),
            _t("Repudiation", "Backend actions may not be attributable", "Medium", [
                "Propagate request correlation ids across services.",
                "Log actor, service identity, request id, and authorization decision.",
            ]),
            _t("Tampering", "Application code or configuration can be changed", "High", [
                "Use signed deployments, immutable artifacts, and CI/CD approvals.",
                "Separate deploy permissions from runtime permissions.",
            ]),
        ],
    },
    "database": {
        "label": "Database",
        "rules": [
            _t("Information Disclosure", "Sensitive records can be exposed", "Critical", [
                "Encrypt data at rest with managed keys or KMS.",
                "Restrict network access and apply least privilege database roles.",
                "Mask or tokenize sensitive attributes where possible.",
            ]),
            _t("Tampering", "Data can be changed without integrity controls", "High", [
                "Use transactions, constraints, audit trails, and change history for sensitive tables.",
                "Monitor abnormal write volume and privileged updates.",
            ]),
            _t("Denial of Service", "Database can be exhausted by expensive queries", "High", [
                "Apply query timeouts, connection pooling, resource limits, and read replicas.",
                "Alert on CPU, locks, storage, and connection saturation.",
            ]),
        ],
    },
    "storage": {
        "label": "Storage",
        "rules": [
            _t("Information Disclosure", "Object storage can expose private files", "High", [
                "Block public access by default and review bucket/container policies.",
                "Encrypt objects and classify sensitive data.",
            ]),
            _t("Tampering", "Stored artifacts can be modified", "Medium", [
                "Enable object versioning and integrity checks.",
                "Use write-once retention for critical evidence or backups.",
            ]),
        ],
    },
    "queue": {
        "label": "Queue",
        "rules": [
            _t("Tampering", "Messages can be altered or replayed", "Medium", [
                "Validate message signatures or integrity fields.",
                "Use idempotency keys and replay protection.",
            ]),
            _t("Denial of Service", "Queue can be flooded with messages", "Medium", [
                "Set message size limits, dead-letter queues, and producer quotas.",
                "Monitor backlog age and processing latency.",
            ]),
        ],
    },
    "identity_provider": {
        "label": "Identity Provider",
        "rules": [
            _t("Spoofing", "Identity provider compromise impacts all dependent services", "Critical", [
                "Enforce MFA and conditional access for privileged identities.",
                "Rotate credentials and monitor risky sign-ins.",
                "Use strong token validation in every relying party.",
            ]),
            _t("Elevation of Privilege", "Excessive roles can grant unauthorized access", "High", [
                "Review role assignments and privileged groups periodically.",
                "Use just-in-time access and approval workflows.",
            ]),
        ],
    },
    "monitoring": {
        "label": "Monitoring/Logs",
        "rules": [
            _t("Repudiation", "Missing or mutable logs reduce forensic capability", "High", [
                "Centralize logs and protect them with immutable retention.",
                "Log authentication, authorization, data access, and administrative actions.",
            ]),
            _t("Information Disclosure", "Logs can contain secrets or personal data", "Medium", [
                "Redact tokens, passwords, and sensitive payload fields.",
                "Restrict log access and audit log queries.",
            ]),
        ],
    },
    "backup": {
        "label": "Backup",
        "rules": [
            _t("Tampering", "Backups can be deleted or encrypted by an attacker", "High", [
                "Use immutable backups and separation of duties.",
                "Store backups in a separate account or region when critical.",
            ]),
            _t("Denial of Service", "Recovery can fail during an incident", "High", [
                "Test restores regularly and document RTO/RPO.",
                "Monitor backup job success and retention policy drift.",
            ]),
        ],
    },
    "secrets_kms": {
        "label": "Secrets/KMS",
        "rules": [
            _t("Information Disclosure", "Secrets or keys can be exposed", "Critical", [
                "Store secrets in a managed vault and rotate them periodically.",
                "Limit decrypt permissions and alert on abnormal key usage.",
            ]),
            _t("Elevation of Privilege", "Overbroad key permissions can unlock sensitive systems", "High", [
                "Use least privilege key policies and separation of duties.",
                "Require approval for key administration operations.",
            ]),
        ],
    },
    "cdn": {
        "label": "CDN",
        "rules": [
            _t("Information Disclosure", "Cached content can expose sensitive responses", "Medium", [
                "Disable caching for authenticated or sensitive endpoints.",
                "Validate cache-control headers and purge workflows.",
            ]),
            _t("Tampering", "Origin or cache configuration can be abused", "Medium", [
                "Restrict origin access to the CDN.",
                "Use signed URLs or signed cookies for protected content.",
            ]),
        ],
    },
}


PROVIDER_KNOWLEDGE: dict[str, dict[str, dict]] = {
    "aws": {
        "api_gateway": {
            "label": "AWS API Gateway",
            "rules": [
                _t("Spoofing", "AWS API Gateway can accept forged identity tokens if authorizers are weak", "High", [
                    "Validate JWT issuer, audience, expiration, and signature in a managed authorizer or Lambda authorizer.",
                    "Use least privilege IAM permissions for integrations and execution roles.",
                ]),
                _t("Tampering", "Request transformation and mapping templates can introduce weak controls", "Medium", [
                    "Enforce request validation and schema checks at the gateway.",
                    "Avoid mapping templates that silently drop or rewrite security-sensitive fields.",
                ]),
            ],
        },
        "database": {
            "label": "AWS Database",
            "rules": [
                _t("Information Disclosure", "AWS databases can expose data through public access or weak security groups", "Critical", [
                    "Keep databases private in VPC subnets and block public exposure.",
                    "Use KMS encryption, security groups, and least privilege database accounts.",
                ]),
            ],
        },
        "storage": {
            "label": "AWS Storage",
            "rules": [
                _t("Information Disclosure", "S3-style storage can leak data through bucket policy drift", "High", [
                    "Block public access by default and review bucket policies regularly.",
                    "Use bucket encryption, object ownership controls, and access logging.",
                ]),
            ],
        },
        "identity_provider": {
            "label": "AWS Identity",
            "rules": [
                _t("Spoofing", "Federated identities can be abused if trust policy or IdP validation is weak", "High", [
                    "Validate SAML/OIDC trust relationships and role session conditions.",
                    "Monitor suspicious role assumption patterns and enforce MFA for privileged flows.",
                ]),
            ],
        },
        "secrets_kms": {
            "label": "AWS Secrets/KMS", 
            "rules": [
                _t("Information Disclosure", "Secrets Manager or KMS misconfiguration can expose credentials", "Critical", [
                    "Restrict decrypt and read permissions to specific workloads.",
                    "Rotate secrets and alert on abnormal key usage or secret reads.",
                ]),
            ],
        },
    },
    "azure": {
        "api_gateway": {
            "label": "Azure API Management",
            "rules": [
                _t("Spoofing", "Azure API Management can be abused when JWT validation or subscription enforcement is weak", "High", [
                    "Enforce JWT validation with issuer and audience checks.",
                    "Use subscription keys, managed identities, and least privilege backend access.",
                ]),
            ],
        },
        "database": {
            "label": "Azure Database",
            "rules": [
                _t("Information Disclosure", "Azure databases can leak data if private endpoints are not used", "Critical", [
                    "Prefer private endpoints and disable public network access.",
                    "Use encryption at rest, RBAC, and monitoring alerts for exposed data paths.",
                ]),
            ],
        },
        "identity_provider": {
            "label": "Azure Entra ID",
            "rules": [
                _t("Spoofing", "Identity compromise in Entra ID impacts downstream workloads", "Critical", [
                    "Require MFA, conditional access, and privileged identity management.",
                    "Review enterprise app permissions and service principal consent.",
                ]),
            ],
        },
        "monitoring": {
            "label": "Azure Monitor",
            "rules": [
                _t("Repudiation", "Logging gaps in Azure Monitor/App Insights reduce forensic visibility", "High", [
                    "Centralize logs in Log Analytics and protect retention policies.",
                    "Track admin actions, authentication events, and data access with immutable retention.",
                ]),
            ],
        },
    },
    "gcp": {
        "api_gateway": {
            "label": "GCP API Gateway",
            "rules": [
                _t("Spoofing", "GCP API Gateway or Cloud Endpoints can accept forged requests if auth is weak", "High", [
                    "Validate OIDC tokens and service account identity.",
                    "Use IAM-based access control and backend service account restrictions.",
                ]),
            ],
        },
        "database": {
            "label": "GCP Cloud SQL / Database",
            "rules": [
                _t("Information Disclosure", "Cloud SQL or managed databases can expose data if public IP or weak IAM is enabled", "Critical", [
                    "Disable public exposure and prefer private IP connectivity.",
                    "Use CMEK when required, database IAM restrictions, and audit logs.",
                ]),
            ],
        },
        "storage": {
            "label": "GCP Cloud Storage",
            "rules": [
                _t("Information Disclosure", "Cloud Storage buckets can leak content through IAM drift or public ACLs", "High", [
                    "Block public access and review bucket IAM bindings.",
                    "Enable uniform bucket-level access and audit access patterns.",
                ]),
            ],
        },
        "identity_provider": {
            "label": "GCP Identity",
            "rules": [
                _t("Spoofing", "GCP identity compromise or overbroad service accounts enable lateral movement", "Critical", [
                    "Apply least privilege IAM and service account scoping.",
                    "Use workforce identity federation or strong MFA for privileged identities.",
                ]),
            ],
        },
        "secrets_kms": {
            "label": "GCP Secret Manager / KMS",
            "rules": [
                _t("Information Disclosure", "Secrets Manager or KMS misuse can expose application secrets", "Critical", [
                    "Restrict secret access to specific service accounts and workloads.",
                    "Rotate secrets and monitor access logs for anomalous reads.",
                ]),
            ],
        },
    },
}


def _is_type(component_id: str, component_type: str, components: list[dict]) -> bool:
    return any(c["id"] == component_id and c["type"] == component_type for c in components)


def _is_external_node(component_id: str, components: list[dict]) -> bool:
    return _is_type(component_id, "internet", components) or _is_type(component_id, "user", components)


def _is_insecure_protocol(value: str) -> bool:
    normalized = str(value or "").strip().lower().replace(" ", "")
    return normalized in {"http", "ftp", "telnet", "smtp", "ldap", "tcp"}


FLOW_RULES: list[dict] = [
    {
        "id": "insecure-protocol-crosses-trust-boundary",
        "when": lambda arch: any(
            f.get("trustBoundary") and _is_insecure_protocol(f.get("protocol", ""))
            for f in arch["flows"]
        ),
        "build": lambda: {
            "stride": "Information Disclosure",
            "title": "Insecure protocol crosses a trust boundary",
            "severity": "Critical",
            "evidence": "A flow crossing a detected trust boundary uses a protocol without transport encryption.",
            "countermeasures": [
                "Replace the protocol with TLS-protected transport and validate peer identities.",
                "Block plaintext protocols at network boundaries and monitor downgrade attempts.",
            ],
            "confidence": 0.90,
        },
    },
    {
        "id": "unknown-protocol-crosses-trust-boundary",
        "when": lambda arch: any(
            f.get("trustBoundary") and str(f.get("protocol") or "unknown").lower() == "unknown"
            for f in arch["flows"]
        ),
        "build": lambda: {
            "stride": "Tampering",
            "title": "Trust-boundary flow has an unverified protocol",
            "severity": "High",
            "evidence": "A flow crosses a trust boundary, but its protocol and protection could not be confirmed from the diagram.",
            "countermeasures": [
                "Confirm the protocol, authentication method, and encryption properties during human review.",
                "Require TLS, certificate validation, and integrity protection for boundary-crossing traffic.",
            ],
            "confidence": 0.68,
        },
    },
    {
        "id": "external-entry-without-waf",
        "when": lambda arch: (
            not any(c["type"] == "waf" for c in arch["components"])
            and any(
                _is_external_node(f["from"], arch["components"]) or _is_external_node(f["to"], arch["components"])
                for f in arch["flows"]
            )
        ),
        "build": lambda: {
            "stride": "Denial of Service",
            "title": "Public flow without explicit WAF or edge filtering",
            "severity": "High",
            "evidence": "The architecture contains an external flow, but no WAF component was detected.",
            "countermeasures": [
                "Place a WAF or equivalent edge control before public APIs.",
                "Add rate limiting, bot mitigation, and DDoS protection at the edge.",
            ],
            "confidence": 0.74,
        },
    },
    {
        "id": "internet-to-api",
        "when": lambda arch: any(
            _is_type(f["from"], "internet", arch["components"]) and _is_type(f["to"], "api_gateway", arch["components"])
            for f in arch["flows"]
        ),
        "build": lambda: {
            "stride": "Spoofing",
            "title": "Internet-facing API requires strong authentication controls",
            "severity": "High",
            "evidence": "A flow from Internet to API Gateway was detected.",
            "countermeasures": [
                "Require OAuth2/OIDC token validation at the API edge.",
                "Use mTLS for high-trust integrations and enforce request signing where applicable.",
            ],
            "confidence": 0.86,
        },
    },
    {
        "id": "compute-to-database",
        "when": lambda arch: any(
            _is_type(f["from"], "compute", arch["components"]) and _is_type(f["to"], "database", arch["components"])
            for f in arch["flows"]
        ),
        "build": lambda: {
            "stride": "Information Disclosure",
            "title": "Backend-to-database flow can expose sensitive data",
            "severity": "Critical",
            "evidence": "A backend compute component communicates with a database.",
            "countermeasures": [
                "Use private networking, database least privilege, and encryption at rest.",
                "Log sensitive data access and alert on abnormal query patterns.",
            ],
            "confidence": 0.84,
        },
    },
    {
        "id": "missing-monitoring",
        "when": lambda arch: not any(c["type"] == "monitoring" for c in arch["components"]),
        "build": lambda: {
            "stride": "Repudiation",
            "title": "Architecture lacks explicit monitoring or logging component",
            "severity": "Medium",
            "evidence": "No monitoring/logging component was detected in the architecture.",
            "countermeasures": [
                "Add centralized audit logging for identity, API, backend, and data access events.",
                "Protect logs with immutable retention and restricted access.",
            ],
            "confidence": 0.68,
        },
    },
    {
        "id": "missing-backup-for-database",
        "when": lambda arch: (
            any(c["type"] == "database" for c in arch["components"])
            and not any(c["type"] == "backup" for c in arch["components"])
        ),
        "build": lambda: {
            "stride": "Denial of Service",
            "title": "Database present without explicit backup component",
            "severity": "High",
            "evidence": "A database was detected, but no backup/recovery component was detected.",
            "countermeasures": [
                "Configure automated backups, retention policy, and restore testing.",
                "Define RTO/RPO and alert on backup job failures.",
            ],
            "confidence": 0.70,
        },
    },
]


def _slug(value: str) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", str(value).lower()))


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _enrich_threat(base: dict, context: dict, default_confidence: float = 0.8) -> dict:
    component_part = f"Component: {context.get('componentName')}. " if context.get("componentName") else ""
    evidence = base.get("evidence") or f"{component_part}Rule source: {context.get('source')}."
    comp_id = context.get("componentId") or "architecture"
    return {
        "id": f"{comp_id}-{_slug(base['stride'])}-{_slug(base['title'])}",
        "stride": base["stride"],
        "title": base["title"],
        "severity": base["severity"],
        "componentId": context.get("componentId"),
        "componentName": context.get("componentName"),
        "evidence": evidence,
        "countermeasures": base["countermeasures"],
        "confidence": _clamp(base.get("confidence") or default_confidence, 0.0, 1.0),
        "source": context.get("source"),
        "ruleId": context.get("ruleId"),
        "securityReferences": SECURITY_REFERENCES.get(base["stride"], []),
        "management": {
            "status": "open",
            "owner": "",
            "justification": "",
            "selectedCountermeasure": "",
            "updatedAt": None,
        },
    }


def _build_component_threats(component: dict) -> list[dict]:
    provider = str(component.get("provider") or "generic").lower()
    knowledge = PROVIDER_KNOWLEDGE.get(provider, {}).get(component["type"])
    if knowledge is None:
        knowledge = COMPONENT_KNOWLEDGE.get(component["type"])
    if not knowledge:
        return [
            _enrich_threat(
                _t("Information Disclosure", "Unknown component requires manual security review", "Medium", [
                    "Classify the component and define applicable controls.",
                    "Review authentication, authorization, logging, and data exposure risks.",
                ]),
                {"componentId": component["id"], "componentName": component["name"], "source": "fallback-rule"},
                component["confidence"],
            )
        ]
    return [
        _enrich_threat(
            rule,
            {
                "componentId": component["id"],
                "componentName": component["name"],
                "source": f"component-rule:{provider}",
            },
            component["confidence"],
        )
        for rule in knowledge["rules"]
    ]


def _compare_threats(threat: dict) -> tuple:
    return (-(SEVERITY_WEIGHT.get(threat["severity"], 0)), -threat["confidence"])


def _normalize_detection_alternatives(raw: dict) -> tuple[list[dict], dict[str, int]]:
    source = raw.get("detectionAlternatives") or []
    alternatives = []
    for alternative in source:
        normalized = deepcopy(alternative)
        normalized.update({
            "id": alternative.get("id"),
            "name": alternative.get("name"),
            "type": alternative.get("type"),
            "provider": alternative.get("provider") or "generic",
            "confidence": _clamp(alternative.get("confidence", 0.75), 0.0, 1.0),
            "bbox": deepcopy(alternative.get("bbox")),
            "ocrLabel": alternative.get("ocrLabel") or (alternative.get("metadata") or {}).get("ocrLabel"),
            "ocrEvidence": deepcopy(
                alternative.get("ocrEvidence") or (alternative.get("metadata") or {}).get("ocrEvidence")
            ),
            "reviewStatus": (
                alternative.get("reviewStatus")
                or (alternative.get("metadata") or {}).get("reviewStatus")
                or "superseded_pending_review"
            ),
            "metadata": deepcopy(alternative.get("metadata") or {}),
        })
        alternatives.append(normalized)
    trace = {
        "inputCount": len(source),
        "outputCount": len(alternatives),
        "alternativeLossCount": len(source) - len(alternatives),
    }
    return alternatives, trace


def normalize_architecture(raw: dict) -> dict:
    components = [
        {
            "id": c.get("id") or f"component_{i + 1}",
            "name": c.get("name") or COMPONENT_KNOWLEDGE.get(c.get("type", ""), {}).get("label") or c.get("type") or "Unknown",
            "type": c.get("type") or "unknown",
            "provider": c.get("provider") or "generic",
            "confidence": _clamp(c.get("confidence", 0.75), 0.0, 1.0),
            "bbox": c.get("bbox"),
            "ocrLabel": c.get("ocrLabel") or (c.get("metadata") or {}).get("ocrLabel"),
            "ocrEvidence": c.get("ocrEvidence") or (c.get("metadata") or {}).get("ocrEvidence"),
            "reviewStatus": c.get("reviewStatus") or (c.get("metadata") or {}).get("reviewStatus") or "unreviewed",
            "metadata": c.get("metadata") or {},
        }
        for i, c in enumerate(raw.get("components") or [])
    ]
    flows = [
        {
            "id": f.get("id") or f"flow_{i + 1}",
            "from": f.get("from"),
            "to": f.get("to"),
            "protocol": f.get("protocol") or "unknown",
            "trustBoundary": bool(f.get("trustBoundary")),
            "confidence": _clamp(f.get("confidence", 0.5), 0.0, 1.0),
            "inferred": bool(f.get("inferred")),
            "reviewStatus": f.get("reviewStatus") or "unreviewed",
            "evidence": f.get("evidence") or "json_input",
            "directionEvidence": f.get("directionEvidence"),
            "directionConfidence": _clamp(f.get("directionConfidence", 0.5), 0.0, 1.0),
            "arrowheadScores": f.get("arrowheadScores") or {},
            "crossedBoundaryIds": f.get("crossedBoundaryIds") or [],
            "protocolEvidence": f.get("protocolEvidence"),
        }
        for i, f in enumerate(raw.get("flows") or [])
    ]
    detection_alternatives, alternative_trace = _normalize_detection_alternatives(raw)
    return {
        "name": raw.get("name") or "Untitled architecture",
        "sourceImage": raw.get("sourceImage"),
        "detectionAlternatives": detection_alternatives,
        "detectionAlternativeTrace": alternative_trace,
        "components": components,
        "flows": flows,
        "trustBoundaries": raw.get("trustBoundaries") or [],
        "notes": raw.get("notes") or [],
        "detectedBy": raw.get("detectedBy") or "json_input",
        "detectorModel": raw.get("detectorModel"),
        "detectorMetadata": raw.get("detectorMetadata") or {},
        "structureMetadata": raw.get("structureMetadata") or {},
        "flowStrategy": raw.get("flowStrategy") or "legacy",
        "flowStrategyTrace": deepcopy(raw.get("flowStrategyTrace") or {}),
        "ocrMetadata": raw.get("ocrMetadata") or {},
        "reviewRequired": bool(raw.get("reviewRequired")),
        "reviewedByHuman": bool(raw.get("reviewedByHuman")),
        "reviewItems": raw.get("reviewItems") or [],
        "threatManagement": raw.get("threatManagement") or {},
    }


def calculate_risk_score(threats: list[dict], components: list[dict]) -> dict:
    if not threats:
        return {"value": 0, "label": "Low", "summary": "No threats were generated from the current architecture input."}
    weighted = sum((SEVERITY_WEIGHT.get(t["severity"], 3)) * t["confidence"] for t in threats)
    average = weighted / len(threats)
    exposure_bonus = 0.8 if any(c["type"] == "internet" for c in components) else 0.0
    sensitive_bonus = 0.7 if any(c["type"] in ("database", "secrets_kms") for c in components) else 0.0
    value = round(_clamp(round((average + exposure_bonus + sensitive_bonus) * 10) / 10, 0, 10), 1)
    label = "Critical" if value >= 8 else "High" if value >= 6 else "Medium" if value >= 3.5 else "Low"
    summaries = {
        "Critical": "The architecture has high-impact assets and exposed paths that require immediate security review.",
        "High": "The architecture contains meaningful risks that should be prioritized before production release.",
        "Medium": "The architecture has relevant risks; the controls and exposure should be reviewed in context.",
        "Low": "The architecture appears to have limited risk based on detected components, pending human review.",
    }
    return {"value": value, "label": label, "summary": summaries[label]}


def apply_threat_management(threats: list[dict], decisions: dict | None) -> list[dict]:
    """Overlay human decisions without allowing them to mutate generated threat facts."""
    decisions = decisions if isinstance(decisions, dict) else {}
    managed: list[dict] = []
    for threat in threats:
        supplied = decisions.get(threat["id"], {})
        supplied = supplied if isinstance(supplied, dict) else {}
        status = supplied.get("status", "open")
        if status not in THREAT_STATUSES:
            status = "open"
        management = {
            "status": status,
            "owner": str(supplied.get("owner") or "").strip(),
            "justification": str(supplied.get("justification") or "").strip(),
            "selectedCountermeasure": str(supplied.get("selectedCountermeasure") or "").strip(),
            "updatedAt": supplied.get("updatedAt"),
        }
        managed.append({**threat, "management": management})
    return managed


def calculate_risk_comparison(threats: list[dict], components: list[dict]) -> dict:
    inherent = calculate_risk_score(threats, components)
    residual_threats = []
    counts = {status: 0 for status in sorted(THREAT_STATUSES)}
    for threat in threats:
        status = (threat.get("management") or {}).get("status", "open")
        status = status if status in THREAT_STATUSES else "open"
        counts[status] += 1
        factor = 0.35 if status == "mitigated" else 0.0 if status == "false_positive" else 1.0
        residual_threats.append({**threat, "confidence": threat["confidence"] * factor})
    residual = calculate_risk_score(residual_threats, components)
    return {
        "inherent": inherent,
        "residual": residual,
        "reduction": round(max(0.0, inherent["value"] - residual["value"]), 1),
        "counts": counts,
    }


def calculate_coverage(threats: list[dict]) -> dict[str, int]:
    return {stride: sum(1 for t in threats if t["stride"] == stride) for stride in STRIDE_ORDER}


def build_graph(architecture: dict) -> dict:
    return {
        "nodes": [
            {"id": c["id"], "label": c["name"], "type": c["type"], "confidence": c["confidence"]}
            for c in architecture["components"]
        ],
        "edges": [
            {
                "id": f["id"],
                "from": f["from"],
                "to": f["to"],
                "label": f["protocol"],
                "trustBoundary": f["trustBoundary"],
                "inferred": f["inferred"],
                "confidence": f["confidence"],
                "evidence": f["evidence"],
            }
            for f in architecture["flows"]
        ],
    }


def generate_markdown_report(
    architecture: dict,
    threats: list[dict],
    score: dict,
    coverage: dict,
    risk_comparison: dict | None = None,
) -> str:
    risk_comparison = risk_comparison or {
        "inherent": score,
        "residual": score,
        "reduction": 0.0,
        "counts": {"open": len(threats), "mitigated": 0, "accepted": 0, "false_positive": 0},
    }
    lines = [
        "# ThreatLens AI — STRIDE Threat Modeling Report",
        "",
        f"**Architecture:** {architecture['name']}",
        f"**Overall risk:** {score['label']} ({score['value']}/10)",
        f"**Components detected:** {len(architecture['components'])}",
        f"**Threats generated:** {len(threats)}",
        "",
        "## Executive summary",
        score["summary"],
        "",
        "## Risk treatment summary",
        f"- Inherent risk: {risk_comparison['inherent']['label']} ({risk_comparison['inherent']['value']}/10)",
        f"- Residual risk: {risk_comparison['residual']['label']} ({risk_comparison['residual']['value']}/10)",
        f"- Reduction after controls: {risk_comparison['reduction']} points",
        f"- Open: {risk_comparison['counts'].get('open', 0)}; mitigated: {risk_comparison['counts'].get('mitigated', 0)}; accepted: {risk_comparison['counts'].get('accepted', 0)}; false positive: {risk_comparison['counts'].get('false_positive', 0)}",
        "",
        "## STRIDE coverage",
    ]
    for stride in STRIDE_ORDER:
        lines.append(f"- {stride}: {coverage.get(stride, 0)}")
    lines += ["", "## Components detected"]
    for c in architecture["components"]:
        lines.append(f"- {c['name']} (`{c['type']}`) — confidence {round(c['confidence'] * 100)}%")
    alternatives = architecture.get("detectionAlternatives") or []
    if alternatives:
        lines += [
            "",
            "## Detection alternatives pending review",
            (
                f"{len(alternatives)} superseded detection alternative(s) are retained for review only. "
                "They are excluded from the architecture graph, STRIDE analysis, and risk calculation."
            ),
        ]
        for alternative in alternatives:
            metadata = alternative.get("metadata") or {}
            lines.append(
                f"- `{alternative['id']}`: {alternative['name']} (`{alternative['type']}`, "
                f"provider {alternative['provider']}, confidence {round(alternative['confidence'] * 100)}%) "
                f"- superseded by `{metadata['supersededBy']}`; "
                f"reason: {metadata.get('supersededReason') or 'not provided'}"
            )
    lines += ["", "## Data flows and trust boundaries"]
    if architecture["flows"]:
        for flow in architecture["flows"]:
            boundary = "; crosses trust boundary" if flow["trustBoundary"] else ""
            protocol_source = (
                f"; protocol OCR {round(flow['protocolEvidence']['ocrConfidence'] * 100)}%"
                if flow.get("protocolEvidence")
                else ""
            )
            lines.append(
                f"- `{flow['from']}` -> `{flow['to']}` via {flow['protocol']} "
                f"(confidence {round(flow['confidence'] * 100)}%; evidence: {flow['evidence']}"
                f"{protocol_source}{boundary})"
            )
    else:
        lines.append("- No data flows were confirmed from the current input.")
    if architecture["trustBoundaries"]:
        for boundary in architecture["trustBoundaries"]:
            members = ", ".join(boundary.get("componentIds") or []) or "membership pending review"
            lines.append(f"- Trust boundary: {boundary.get('name', 'Unnamed')} ({members})")
    lines += ["", "## Prioritized threats"]
    for item in threats[:12]:
        management = item.get("management") or {}
        lines += [
            f"### {item['severity']} — {item['stride']}: {item['title']}",
            f"**Evidence:** {item['evidence']}",
            f"**Confidence:** {round(item['confidence'] * 100)}%",
            f"**Treatment:** {management.get('status', 'open')}"
            + (f"; owner: {management['owner']}" if management.get("owner") else ""),
            "**Countermeasures:**",
        ]
        for measure in item["countermeasures"]:
            lines.append(f"- {measure}")
        references = item.get("securityReferences") or []
        if references:
            lines.append("**Security references:** " + "; ".join(
                f"[{ref['id']}]({ref['url']}) {ref['title']}" for ref in references
            ))
        lines.append("")
    lines += ["## Mitigation plan"]
    planned = [t for t in threats if (t.get("management") or {}).get("status") in {"open", "mitigated"}]
    if not planned:
        lines.append("- No open mitigation actions were recorded.")
    for item in planned[:20]:
        management = item.get("management") or {}
        selected = management.get("selectedCountermeasure") or item["countermeasures"][0]
        owner = management.get("owner") or "Unassigned"
        lines.append(f"- [{management.get('status', 'open')}] {item['title']} — {selected} (owner: {owner})")
    lines += [""]
    lines += [
        "## Human review checklist",
        "- Confirm if all public entry points were detected.",
        "- Confirm if data stores contain sensitive or regulated data.",
        "- Confirm if trust boundaries and protocols are correctly represented.",
        "- Review low-confidence detections before accepting the final risk score.",
    ]
    return "\n".join(lines)


def ensure_detection_alternatives_in_report(report: str, architecture: dict) -> str:
    alternatives = architecture.get("detectionAlternatives") or []
    heading = "## Detection alternatives pending review"
    if not alternatives or heading.lower() in report.lower():
        return report
    lines = [
        report.rstrip(),
        "",
        heading,
        (
            f"{len(alternatives)} superseded detection alternative(s) are retained for review only. "
            "They are excluded from the architecture graph, STRIDE analysis, and risk calculation."
        ),
    ]
    for alternative in alternatives:
        metadata = alternative.get("metadata") or {}
        lines.append(
            f"- `{alternative['id']}`: {alternative['name']} (`{alternative['type']}`, "
            f"provider {alternative['provider']}, confidence {round(alternative['confidence'] * 100)}%) "
            f"- superseded by `{metadata['supersededBy']}`; "
            f"reason: {metadata.get('supersededReason') or 'not provided'}"
        )
    return "\n".join(lines)


def analyze_architecture(raw: dict) -> dict:
    architecture = normalize_architecture(raw)
    component_threats = [t for c in architecture["components"] for t in _build_component_threats(c)]
    flow_threats = []
    for rule in FLOW_RULES:
        if rule["when"](architecture):
            built = rule["build"]()
            flow_threats.append(_enrich_threat(built, {"source": "flow-rule", "componentId": "architecture", "componentName": "Architecture", "ruleId": rule["id"]}))
    threats = sorted(component_threats + flow_threats, key=_compare_threats)
    threats = apply_threat_management(threats, architecture.get("threatManagement"))
    score = calculate_risk_score(threats, architecture["components"])
    risk_comparison = calculate_risk_comparison(threats, architecture["components"])
    coverage = calculate_coverage(threats)
    graph = build_graph(architecture)
    report_markdown = generate_markdown_report(architecture, threats, score, coverage, risk_comparison)
    return {
        "architecture": architecture,
        "threats": threats,
        "score": score,
        "riskComparison": risk_comparison,
        "coverage": coverage,
        "graph": graph,
        "reportMarkdown": report_markdown,
    }


COMPONENT_TYPES: list[str] = list(COMPONENT_KNOWLEDGE.keys())
