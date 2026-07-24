# Relatório de exemplo de modelagem de ameaças

> Resultado gerado por uma execução real do MVP 1.0.0-mvp. Os componentes e fluxos
> são inferências automáticas e permanecem sujeitos à revisão humana.

## Arquitetura analisada

- Imagem: `data/sample-diagrams/02-mixed-components.jpg`.
- Detector: `yolo`.
- Estratégia de fluxos: `legacy`.
- Componentes detectados: 8.
- Fluxos inferidos: 13.
- Ameaças geradas: 23.
- Risco: Medium (4.4/10).

## Componentes detectados

| ID | Nome | Tipo | Provider | Confiança | Revisão |
| --- | --- | --- | --- | ---: | --- |
| compute_1 | Compute | compute | generic | 0.462 | pending |
| api_gateway_1 | Api Gateway | api_gateway | generic | 0.433 | pending |
| storage_1 | Storage | storage | generic | 0.376 | pending |
| monitoring_1 | Monitoring | monitoring | generic | 0.373 | pending |
| database_1 | Database | database | generic | 0.345 | pending |
| cdn_1 | Cdn | cdn | generic | 0.301 | pending |
| internet_1 | Internet | internet | generic | 0.292 | pending |
| user_1 | User | user | generic | 0.185 | pending |

## Fluxos inferidos

| ID | Origem | Destino | Protocolo | Confiança | Evidência |
| --- | --- | --- | --- | ---: | --- |
| f1 | internet_1 | cdn_1 | unknown | 0.795 | detected_line |
| f2 | database_1 | compute_1 | unknown | 0.793 | detected_line |
| f3 | cdn_1 | api_gateway_1 | unknown | 0.792 | detected_line |
| f4 | database_1 | storage_1 | unknown | 0.791 | detected_line |
| f5 | internet_1 | user_1 | unknown | 0.758 | segment_graph |
| f6 | database_1 | api_gateway_1 | unknown | 0.757 | segment_graph |
| f7 | user_1 | cdn_1 | unknown | 0.752 | detected_line |
| f8 | monitoring_1 | storage_1 | unknown | 0.751 | segment_graph |
| f9 | monitoring_1 | database_1 | unknown | 0.75 | detected_line |
| f10 | database_1 | cdn_1 | unknown | 0.75 | detected_line |
| f11 | internet_1 | compute_1 | unknown | 0.748 | detected_line |
| f12 | api_gateway_1 | storage_1 | unknown | 0.746 | detected_line |
| f13 | monitoring_1 | cdn_1 | unknown | 0.743 | segment_graph |

## Ameaças STRIDE, vulnerabilidades e contramedidas

| STRIDE | Severidade | Ativo | Vulnerabilidade | Contramedidas |
| --- | --- | --- | --- | --- |
| Information Disclosure | Critical | Database | Sensitive records can be exposed | Encrypt data at rest with managed keys or KMS.; Restrict network access and apply least privilege database roles.; Mask or tokenize sensitive attributes where possible. |
| Denial of Service | High | Architecture | Public flow without explicit WAF or edge filtering | Place a WAF or equivalent edge control before public APIs.; Add rate limiting, bot mitigation, and DDoS protection at the edge. |
| Denial of Service | High | Architecture | Database present without explicit backup component | Configure automated backups, retention policy, and restore testing.; Define RTO/RPO and alert on backup job failures. |
| Tampering | High | Architecture | Trust-boundary flow has an unverified protocol | Confirm the protocol, authentication method, and encryption properties during human review.; Require TLS, certificate validation, and integrity protection for boundary-crossing traffic. |
| Elevation of Privilege | High | Compute | Compromised workload can gain broader permissions | Use least privilege IAM roles and avoid long-lived credentials.; Harden runtime, patch dependencies, and isolate workloads by trust level. |
| Tampering | High | Compute | Application code or configuration can be changed | Use signed deployments, immutable artifacts, and CI/CD approvals.; Separate deploy permissions from runtime permissions. |
| Spoofing | High | Api Gateway | API clients can forge identity or tokens | Validate JWT issuer, audience, expiration, and signature.; Use OAuth2/OIDC and mTLS for service-to-service integrations.; Apply least privilege scopes per endpoint. |
| Tampering | High | Api Gateway | Request payload can be modified before reaching backend | Validate schemas at the gateway and backend.; Reject unexpected fields and enforce content-type restrictions. |
| Denial of Service | High | Api Gateway | API endpoint can be overloaded | Enable throttling, quotas, circuit breakers, and request size limits.; Add alerts for latency spikes and unusual request volume. |
| Information Disclosure | High | Storage | Object storage can expose private files | Block public access by default and review bucket/container policies.; Encrypt objects and classify sensitive data. |
| Repudiation | High | Monitoring | Missing or mutable logs reduce forensic capability | Centralize logs and protect them with immutable retention.; Log authentication, authorization, data access, and administrative actions. |
| Tampering | High | Database | Data can be changed without integrity controls | Use transactions, constraints, audit trails, and change history for sensitive tables.; Monitor abnormal write volume and privileged updates. |
| Denial of Service | High | Database | Database can be exhausted by expensive queries | Apply query timeouts, connection pooling, resource limits, and read replicas.; Alert on CPU, locks, storage, and connection saturation. |
| Denial of Service | High | Internet | Public entry point can be abused by high traffic | Use rate limiting, WAF rules, bot protection, and autoscaling.; Define abuse thresholds and monitoring alerts for public endpoints. |
| Tampering | High | Internet | Traffic can be altered if transport is weak | Enforce HTTPS/TLS 1.2+ end to end.; Reject insecure protocols and redirect HTTP to HTTPS. |
| Repudiation | Medium | Compute | Backend actions may not be attributable | Propagate request correlation ids across services.; Log actor, service identity, request id, and authorization decision. |
| Information Disclosure | Medium | Api Gateway | API responses can expose sensitive data | Filter sensitive fields before response serialization.; Use consistent error handling that does not leak stack traces or secrets. |
| Tampering | Medium | Storage | Stored artifacts can be modified | Enable object versioning and integrity checks.; Use write-once retention for critical evidence or backups. |
| Information Disclosure | Medium | Monitoring | Logs can contain secrets or personal data | Redact tokens, passwords, and sensitive payload fields.; Restrict log access and audit log queries. |
| Information Disclosure | Medium | Cdn | Cached content can expose sensitive responses | Disable caching for authenticated or sensitive endpoints.; Validate cache-control headers and purge workflows. |
| Tampering | Medium | Cdn | Origin or cache configuration can be abused | Restrict origin access to the CDN.; Use signed URLs or signed cookies for protected content. |
| Spoofing | Medium | User | User identity can be impersonated | Require strong authentication with MFA for privileged flows.; Use short-lived sessions and secure cookie attributes.; Bind sensitive actions to re-authentication. |
| Repudiation | Medium | User | User actions may not be traceable | Log security-relevant actions with user id, source, timestamp, and request correlation id.; Protect audit logs against deletion or tampering. |

## Limitações desta execução

- A execução gerou 44 itens para revisão humana.
- A imagem é sintética e faz parte do conjunto gerado pelo projeto; não demonstra generalização.
- Protocolos ausentes no diagrama permanecem `unknown` e não são inventados.
- Fluxos inferidos por geometria podem conter conexões extras, ausentes ou invertidas.
- A estratégia utilizada foi `legacy`; a estratégia controlada continua experimental e opt-in.
- O relatório usa regras determinísticas e RAG local; chamadas remotas estavam desativadas.
