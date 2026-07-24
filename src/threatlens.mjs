const SEVERITY_WEIGHT = {
  Critical: 10,
  High: 8,
  Medium: 5,
  Low: 2
};

const STRIDE_ORDER = [
  "Spoofing",
  "Tampering",
  "Repudiation",
  "Information Disclosure",
  "Denial of Service",
  "Elevation of Privilege"
];

const COMPONENT_KNOWLEDGE = {
  user: {
    label: "User",
    rules: [
      threat("Spoofing", "User identity can be impersonated", "Medium", [
        "Require strong authentication with MFA for privileged flows.",
        "Use short-lived sessions and secure cookie attributes.",
        "Bind sensitive actions to re-authentication."
      ]),
      threat("Repudiation", "User actions may not be traceable", "Medium", [
        "Log security-relevant actions with user id, source, timestamp, and request correlation id.",
        "Protect audit logs against deletion or tampering."
      ])
    ]
  },
  internet: {
    label: "Internet",
    rules: [
      threat("Denial of Service", "Public entry point can be abused by high traffic", "High", [
        "Use rate limiting, WAF rules, bot protection, and autoscaling.",
        "Define abuse thresholds and monitoring alerts for public endpoints."
      ]),
      threat("Tampering", "Traffic can be altered if transport is weak", "High", [
        "Enforce HTTPS/TLS 1.2+ end to end.",
        "Reject insecure protocols and redirect HTTP to HTTPS."
      ])
    ]
  },
  api_gateway: {
    label: "API Gateway",
    rules: [
      threat("Spoofing", "API clients can forge identity or tokens", "High", [
        "Validate JWT issuer, audience, expiration, and signature.",
        "Use OAuth2/OIDC and mTLS for service-to-service integrations.",
        "Apply least privilege scopes per endpoint."
      ]),
      threat("Tampering", "Request payload can be modified before reaching backend", "High", [
        "Validate schemas at the gateway and backend.",
        "Reject unexpected fields and enforce content-type restrictions."
      ]),
      threat("Denial of Service", "API endpoint can be overloaded", "High", [
        "Enable throttling, quotas, circuit breakers, and request size limits.",
        "Add alerts for latency spikes and unusual request volume."
      ]),
      threat("Information Disclosure", "API responses can expose sensitive data", "Medium", [
        "Filter sensitive fields before response serialization.",
        "Use consistent error handling that does not leak stack traces or secrets."
      ])
    ]
  },
  load_balancer: {
    label: "Load Balancer",
    rules: [
      threat("Tampering", "Traffic routing can be manipulated", "Medium", [
        "Restrict administration to trusted identities.",
        "Use health checks and signed configuration change workflows."
      ]),
      threat("Denial of Service", "Load balancer can become a shared bottleneck", "High", [
        "Enable autoscaling, connection limits, and DDoS protection.",
        "Monitor saturation, failed health checks, and dropped connections."
      ])
    ]
  },
  waf: {
    label: "WAF",
    rules: [
      threat("Tampering", "Weak WAF policy can allow malicious payloads", "Medium", [
        "Enable managed rules for injection, XSS, protocol anomalies, and known bad IPs.",
        "Review false positives and tune rules with change control."
      ]),
      threat("Denial of Service", "WAF bypass or weak rate policy can allow abuse", "Medium", [
        "Combine WAF with rate limiting, bot mitigation, and DDoS protection.",
        "Alert on blocked requests and sudden rule hit changes."
      ])
    ]
  },
  compute: {
    label: "Compute/Server",
    rules: [
      threat("Elevation of Privilege", "Compromised workload can gain broader permissions", "High", [
        "Use least privilege IAM roles and avoid long-lived credentials.",
        "Harden runtime, patch dependencies, and isolate workloads by trust level."
      ]),
      threat("Repudiation", "Backend actions may not be attributable", "Medium", [
        "Propagate request correlation ids across services.",
        "Log actor, service identity, request id, and authorization decision."
      ]),
      threat("Tampering", "Application code or configuration can be changed", "High", [
        "Use signed deployments, immutable artifacts, and CI/CD approvals.",
        "Separate deploy permissions from runtime permissions."
      ])
    ]
  },
  database: {
    label: "Database",
    rules: [
      threat("Information Disclosure", "Sensitive records can be exposed", "Critical", [
        "Encrypt data at rest with managed keys or KMS.",
        "Restrict network access and apply least privilege database roles.",
        "Mask or tokenize sensitive attributes where possible."
      ]),
      threat("Tampering", "Data can be changed without integrity controls", "High", [
        "Use transactions, constraints, audit trails, and change history for sensitive tables.",
        "Monitor abnormal write volume and privileged updates."
      ]),
      threat("Denial of Service", "Database can be exhausted by expensive queries", "High", [
        "Apply query timeouts, connection pooling, resource limits, and read replicas.",
        "Alert on CPU, locks, storage, and connection saturation."
      ])
    ]
  },
  storage: {
    label: "Storage",
    rules: [
      threat("Information Disclosure", "Object storage can expose private files", "High", [
        "Block public access by default and review bucket/container policies.",
        "Encrypt objects and classify sensitive data."
      ]),
      threat("Tampering", "Stored artifacts can be modified", "Medium", [
        "Enable object versioning and integrity checks.",
        "Use write-once retention for critical evidence or backups."
      ])
    ]
  },
  queue: {
    label: "Queue",
    rules: [
      threat("Tampering", "Messages can be altered or replayed", "Medium", [
        "Validate message signatures or integrity fields.",
        "Use idempotency keys and replay protection."
      ]),
      threat("Denial of Service", "Queue can be flooded with messages", "Medium", [
        "Set message size limits, dead-letter queues, and producer quotas.",
        "Monitor backlog age and processing latency."
      ])
    ]
  },
  identity_provider: {
    label: "Identity Provider",
    rules: [
      threat("Spoofing", "Identity provider compromise impacts all dependent services", "Critical", [
        "Enforce MFA and conditional access for privileged identities.",
        "Rotate credentials and monitor risky sign-ins.",
        "Use strong token validation in every relying party."
      ]),
      threat("Elevation of Privilege", "Excessive roles can grant unauthorized access", "High", [
        "Review role assignments and privileged groups periodically.",
        "Use just-in-time access and approval workflows."
      ])
    ]
  },
  monitoring: {
    label: "Monitoring/Logs",
    rules: [
      threat("Repudiation", "Missing or mutable logs reduce forensic capability", "High", [
        "Centralize logs and protect them with immutable retention.",
        "Log authentication, authorization, data access, and administrative actions."
      ]),
      threat("Information Disclosure", "Logs can contain secrets or personal data", "Medium", [
        "Redact tokens, passwords, and sensitive payload fields.",
        "Restrict log access and audit log queries."
      ])
    ]
  },
  backup: {
    label: "Backup",
    rules: [
      threat("Tampering", "Backups can be deleted or encrypted by an attacker", "High", [
        "Use immutable backups and separation of duties.",
        "Store backups in a separate account or region when critical."
      ]),
      threat("Denial of Service", "Recovery can fail during an incident", "High", [
        "Test restores regularly and document RTO/RPO.",
        "Monitor backup job success and retention policy drift."
      ])
    ]
  },
  secrets_kms: {
    label: "Secrets/KMS",
    rules: [
      threat("Information Disclosure", "Secrets or keys can be exposed", "Critical", [
        "Store secrets in a managed vault and rotate them periodically.",
        "Limit decrypt permissions and alert on abnormal key usage."
      ]),
      threat("Elevation of Privilege", "Overbroad key permissions can unlock sensitive systems", "High", [
        "Use least privilege key policies and separation of duties.",
        "Require approval for key administration operations."
      ])
    ]
  },
  cdn: {
    label: "CDN",
    rules: [
      threat("Information Disclosure", "Cached content can expose sensitive responses", "Medium", [
        "Disable caching for authenticated or sensitive endpoints.",
        "Validate cache-control headers and purge workflows."
      ]),
      threat("Tampering", "Origin or cache configuration can be abused", "Medium", [
        "Restrict origin access to the CDN.",
        "Use signed URLs or signed cookies for protected content."
      ])
    ]
  }
};

const FLOW_RULES = [
  {
    id: "insecure-protocol-crosses-trust-boundary",
    when: ({ flows }) => flows.some((flow) => flow.trustBoundary && isInsecureProtocol(flow.protocol)),
    build: () => ({
      stride: "Information Disclosure",
      title: "Insecure protocol crosses a trust boundary",
      severity: "Critical",
      evidence: "A flow crossing a detected trust boundary uses a protocol without transport encryption.",
      countermeasures: [
        "Replace the protocol with TLS-protected transport and validate peer identities.",
        "Block plaintext protocols at network boundaries and monitor downgrade attempts."
      ],
      confidence: 0.9
    })
  },
  {
    id: "unknown-protocol-crosses-trust-boundary",
    when: ({ flows }) => flows.some((flow) => flow.trustBoundary && flow.protocol.toLowerCase() === "unknown"),
    build: () => ({
      stride: "Tampering",
      title: "Trust-boundary flow has an unverified protocol",
      severity: "High",
      evidence: "A flow crosses a trust boundary, but its protocol and protection could not be confirmed from the diagram.",
      countermeasures: [
        "Confirm the protocol, authentication method, and encryption properties during human review.",
        "Require TLS, certificate validation, and integrity protection for boundary-crossing traffic."
      ],
      confidence: 0.68
    })
  },
  {
    id: "external-entry-without-waf",
    when: ({ components, flows }) => {
      const hasWaf = components.some((item) => item.type === "waf");
      const hasExternalFlow = flows.some((flow) => isExternalNode(flow.from, components) || isExternalNode(flow.to, components));
      return hasExternalFlow && !hasWaf;
    },
    build: () => ({
      stride: "Denial of Service",
      title: "Public flow without explicit WAF or edge filtering",
      severity: "High",
      evidence: "The architecture contains an external flow, but no WAF component was detected.",
      countermeasures: [
        "Place a WAF or equivalent edge control before public APIs.",
        "Add rate limiting, bot mitigation, and DDoS protection at the edge."
      ],
      confidence: 0.74
    })
  },
  {
    id: "internet-to-api",
    when: ({ components, flows }) =>
      flows.some((flow) => isType(flow.from, "internet", components) && isType(flow.to, "api_gateway", components)),
    build: () => ({
      stride: "Spoofing",
      title: "Internet-facing API requires strong authentication controls",
      severity: "High",
      evidence: "A flow from Internet to API Gateway was detected.",
      countermeasures: [
        "Require OAuth2/OIDC token validation at the API edge.",
        "Use mTLS for high-trust integrations and enforce request signing where applicable."
      ],
      confidence: 0.86
    })
  },
  {
    id: "compute-to-database",
    when: ({ components, flows }) =>
      flows.some((flow) => isType(flow.from, "compute", components) && isType(flow.to, "database", components)),
    build: () => ({
      stride: "Information Disclosure",
      title: "Backend-to-database flow can expose sensitive data",
      severity: "Critical",
      evidence: "A backend compute component communicates with a database.",
      countermeasures: [
        "Use private networking, database least privilege, and encryption at rest.",
        "Log sensitive data access and alert on abnormal query patterns."
      ],
      confidence: 0.84
    })
  },
  {
    id: "missing-monitoring",
    when: ({ components }) => !components.some((item) => item.type === "monitoring"),
    build: () => ({
      stride: "Repudiation",
      title: "Architecture lacks explicit monitoring or logging component",
      severity: "Medium",
      evidence: "No monitoring/logging component was detected in the architecture.",
      countermeasures: [
        "Add centralized audit logging for identity, API, backend, and data access events.",
        "Protect logs with immutable retention and restricted access."
      ],
      confidence: 0.68
    })
  },
  {
    id: "missing-backup-for-database",
    when: ({ components }) =>
      components.some((item) => item.type === "database") && !components.some((item) => item.type === "backup"),
    build: () => ({
      stride: "Denial of Service",
      title: "Database present without explicit backup component",
      severity: "High",
      evidence: "A database was detected, but no backup/recovery component was detected.",
      countermeasures: [
        "Configure automated backups, retention policy, and restore testing.",
        "Define RTO/RPO and alert on backup job failures."
      ],
      confidence: 0.7
    })
  }
];

export function analyzeArchitecture(input) {
  const architecture = normalizeArchitecture(input);
  const componentThreats = architecture.components.flatMap((component) => buildComponentThreats(component));
  const flowThreats = FLOW_RULES
    .filter((rule) => rule.when(architecture))
    .map((rule) => enrichThreat(rule.build(), {
      source: "flow-rule",
      componentId: "architecture",
      componentName: "Architecture",
      ruleId: rule.id
    }));

  const threats = [...componentThreats, ...flowThreats].sort(compareThreats);
  const score = calculateRiskScore(threats, architecture.components);
  const coverage = calculateCoverage(threats);
  const graph = buildGraph(architecture);

  return {
    architecture,
    threats,
    score,
    coverage,
    graph,
    reportMarkdown: generateMarkdownReport({ architecture, threats, score, coverage })
  };
}

export function normalizeArchitecture(input) {
  const components = (input.components || []).map((component, index) => ({
    id: component.id || `component_${index + 1}`,
    name: component.name || COMPONENT_KNOWLEDGE[component.type]?.label || component.type || "Unknown",
    type: component.type || "unknown",
    provider: component.provider || "generic",
    confidence: clampNumber(component.confidence ?? 0.75, 0, 1),
    bbox: component.bbox || null,
    ocrLabel: component.ocrLabel || component.metadata?.ocrLabel || null,
    ocrEvidence: component.ocrEvidence || component.metadata?.ocrEvidence || null,
    reviewStatus: component.reviewStatus || component.metadata?.reviewStatus || "unreviewed",
    metadata: component.metadata || {}
  }));

  const flows = (input.flows || []).map((flow, index) => ({
    id: flow.id || `flow_${index + 1}`,
    from: flow.from,
    to: flow.to,
    protocol: flow.protocol || "unknown",
    trustBoundary: Boolean(flow.trustBoundary),
    confidence: clampNumber(flow.confidence ?? 0.5, 0, 1),
    inferred: Boolean(flow.inferred),
    reviewStatus: flow.reviewStatus || "unreviewed",
    evidence: flow.evidence || "json_input",
    directionEvidence: flow.directionEvidence || null,
    directionConfidence: clampNumber(flow.directionConfidence ?? 0.5, 0, 1),
    arrowheadScores: flow.arrowheadScores || {},
    crossedBoundaryIds: flow.crossedBoundaryIds || [],
    protocolEvidence: flow.protocolEvidence || null
  }));

  const detectionAlternatives = (input.detectionAlternatives || []).map((alternative) => ({
    ...alternative,
    id: alternative.id,
    name: alternative.name,
    type: alternative.type,
    provider: alternative.provider || "generic",
    confidence: clampNumber(alternative.confidence ?? 0.75, 0, 1),
    bbox: alternative.bbox || null,
    ocrLabel: alternative.ocrLabel || alternative.metadata?.ocrLabel || null,
    ocrEvidence: alternative.ocrEvidence || alternative.metadata?.ocrEvidence || null,
    reviewStatus: alternative.reviewStatus || alternative.metadata?.reviewStatus || "superseded_pending_review",
    metadata: { ...(alternative.metadata || {}) }
  }));
  const detectionAlternativeTrace = {
    inputCount: (input.detectionAlternatives || []).length,
    outputCount: detectionAlternatives.length,
    alternativeLossCount: (input.detectionAlternatives || []).length - detectionAlternatives.length
  };

  const trustBoundaries = input.trustBoundaries || [];

  return {
    name: input.name || "Untitled architecture",
    sourceImage: input.sourceImage || null,
    components,
    detectionAlternatives,
    detectionAlternativeTrace,
    flows,
    trustBoundaries,
    notes: input.notes || [],
    detectedBy: input.detectedBy || "json_input",
    detectorModel: input.detectorModel || null,
    detectorMetadata: input.detectorMetadata || {},
    structureMetadata: input.structureMetadata || {},
    ocrMetadata: input.ocrMetadata || {},
    reviewRequired: Boolean(input.reviewRequired),
    reviewedByHuman: Boolean(input.reviewedByHuman)
  };
}

export function generateMarkdownReport({ architecture, threats, score, coverage }) {
  const lines = [];
  lines.push(`# ThreatLens AI - STRIDE Threat Modeling Report`);
  lines.push("");
  lines.push(`Architecture: ${architecture.name}`);
  lines.push(`Overall risk: ${score.label} (${score.value}/10)`);
  lines.push(`Components detected: ${architecture.components.length}`);
  lines.push(`Threats generated: ${threats.length}`);
  lines.push("");
  lines.push("## Executive summary");
  lines.push(score.summary);
  lines.push("");
  lines.push("## STRIDE coverage");
  for (const stride of STRIDE_ORDER) {
    lines.push(`- ${stride}: ${coverage[stride] || 0}`);
  }
  lines.push("");
  lines.push("## Components");
  for (const component of architecture.components) {
    lines.push(`- ${component.name} (${component.type}) - confidence ${formatConfidence(component.confidence)}`);
  }
  if (architecture.detectionAlternatives.length) {
    lines.push("");
    lines.push("## Detection alternatives pending review");
    lines.push(`${architecture.detectionAlternatives.length} superseded detection alternative(s) are retained for review only. They are excluded from the architecture graph, STRIDE analysis, and risk calculation.`);
    for (const alternative of architecture.detectionAlternatives) {
      lines.push(`- ${alternative.id}: ${alternative.name} (${alternative.type}, provider ${alternative.provider}, confidence ${formatConfidence(alternative.confidence)}) - superseded by ${alternative.metadata.supersededBy}; reason: ${alternative.metadata.supersededReason || "not provided"}`);
    }
  }
  lines.push("");
  lines.push("## Data flows and trust boundaries");
  if (architecture.flows.length) {
    for (const flow of architecture.flows) {
      const boundary = flow.trustBoundary ? "; crosses trust boundary" : "";
      const protocolSource = flow.protocolEvidence
        ? `; protocol OCR ${formatConfidence(flow.protocolEvidence.ocrConfidence)}`
        : "";
      lines.push(`- ${flow.from} -> ${flow.to} via ${flow.protocol} (confidence ${formatConfidence(flow.confidence)}; evidence: ${flow.evidence}${protocolSource}${boundary})`);
    }
  } else {
    lines.push("- No data flows were confirmed from the current input.");
  }
  for (const boundary of architecture.trustBoundaries) {
    const members = (boundary.componentIds || []).join(", ") || "membership pending review";
    lines.push(`- Trust boundary: ${boundary.name || "Unnamed"} (${members})`);
  }
  lines.push("");
  lines.push("## Prioritized threats");
  for (const item of threats.slice(0, 12)) {
    lines.push(`### ${item.severity} - ${item.stride}: ${item.title}`);
    lines.push(`Evidence: ${item.evidence}`);
    lines.push(`Confidence: ${formatConfidence(item.confidence)}`);
    lines.push("Countermeasures:");
    for (const measure of item.countermeasures) {
      lines.push(`- ${measure}`);
    }
    lines.push("");
  }
  lines.push("## Human review checklist");
  lines.push("- Confirm if all public entry points were detected.");
  lines.push("- Confirm if data stores contain sensitive or regulated data.");
  lines.push("- Confirm if trust boundaries and protocols are correctly represented.");
  lines.push("- Review low-confidence detections before accepting final risk score.");
  return lines.join("\n");
}

function buildComponentThreats(component) {
  const knowledge = COMPONENT_KNOWLEDGE[component.type];
  if (!knowledge) {
    return [
      enrichThreat(
        threat("Information Disclosure", "Unknown component requires manual security review", "Medium", [
          "Classify the component and define applicable controls.",
          "Review authentication, authorization, logging, and data exposure risks."
        ]),
        {
          componentId: component.id,
          componentName: component.name,
          source: "fallback-rule"
        },
        component.confidence
      )
    ];
  }

  return knowledge.rules.map((baseThreat) =>
    enrichThreat(
      baseThreat,
      {
        componentId: component.id,
        componentName: component.name,
        source: "component-rule"
      },
      component.confidence
    )
  );
}

function threat(stride, title, severity, countermeasures) {
  return {
    stride,
    title,
    severity,
    countermeasures
  };
}

function enrichThreat(baseThreat, context, confidence = 0.8) {
  const componentPart = context.componentName ? `Component: ${context.componentName}. ` : "";
  const evidence = baseThreat.evidence || `${componentPart}Rule source: ${context.source}.`;

  return {
    id: `${context.componentId || "architecture"}-${slug(baseThreat.stride)}-${slug(baseThreat.title)}`,
    stride: baseThreat.stride,
    title: baseThreat.title,
    severity: baseThreat.severity,
    componentId: context.componentId || null,
    componentName: context.componentName || null,
    evidence,
    countermeasures: baseThreat.countermeasures,
    confidence: clampNumber(baseThreat.confidence ?? confidence, 0, 1),
    source: context.source,
    ruleId: context.ruleId || null
  };
}

function calculateRiskScore(threats, components) {
  if (!threats.length) {
    return {
      value: 0,
      label: "Low",
      summary: "No threats were generated from the current architecture input."
    };
  }

  const weighted = threats.reduce((total, item) => {
    return total + (SEVERITY_WEIGHT[item.severity] || 3) * item.confidence;
  }, 0);
  const average = weighted / threats.length;
  const exposureBonus = components.some((item) => item.type === "internet") ? 0.8 : 0;
  const sensitiveBonus = components.some((item) => item.type === "database" || item.type === "secrets_kms") ? 0.7 : 0;
  const value = clampNumber(Math.round((average + exposureBonus + sensitiveBonus) * 10) / 10, 0, 10);
  const label = value >= 8 ? "Critical" : value >= 6 ? "High" : value >= 3.5 ? "Medium" : "Low";
  const summary =
    label === "Critical"
      ? "The architecture has high-impact assets and exposed paths that require immediate security review."
      : label === "High"
        ? "The architecture contains meaningful risks that should be prioritized before production release."
        : label === "Medium"
          ? "The architecture has relevant risks, but the current controls and exposure should be reviewed in context."
          : "The architecture appears to have limited risk based on the detected components, pending human review.";

  return { value, label, summary };
}

function calculateCoverage(threats) {
  return STRIDE_ORDER.reduce((acc, stride) => {
    acc[stride] = threats.filter((item) => item.stride === stride).length;
    return acc;
  }, {});
}

function buildGraph(architecture) {
  return {
    nodes: architecture.components.map((component) => ({
      id: component.id,
      label: component.name,
      type: component.type,
      confidence: component.confidence
    })),
    edges: architecture.flows.map((flow) => ({
      id: flow.id,
      from: flow.from,
      to: flow.to,
      label: flow.protocol,
      trustBoundary: flow.trustBoundary,
      inferred: flow.inferred,
      confidence: flow.confidence,
      evidence: flow.evidence
    }))
  };
}

function compareThreats(a, b) {
  const severityDelta = (SEVERITY_WEIGHT[b.severity] || 0) - (SEVERITY_WEIGHT[a.severity] || 0);
  if (severityDelta !== 0) return severityDelta;
  return b.confidence - a.confidence;
}

function isExternalNode(id, components) {
  return isType(id, "internet", components) || isType(id, "user", components);
}

function isInsecureProtocol(value) {
  const normalized = String(value || "").trim().toLowerCase().replaceAll(" ", "");
  return ["http", "ftp", "telnet", "smtp", "ldap", "tcp"].includes(normalized);
}

function isType(id, type, components) {
  return components.some((component) => component.id === id && component.type === type);
}

function clampNumber(value, min, max) {
  return Math.min(max, Math.max(min, Number(value)));
}

function formatConfidence(value) {
  return `${Math.round(value * 100)}%`;
}

function slug(value) {
  return String(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export const STRIDE_CATEGORIES = STRIDE_ORDER;
export const COMPONENT_TYPES = Object.keys(COMPONENT_KNOWLEDGE);
