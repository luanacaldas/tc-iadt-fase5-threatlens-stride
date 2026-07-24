# Reporting and RAG Plan

## Goal

Generate a STRIDE threat modeling report that is useful, explainable, and grounded in detected architecture evidence.

## Knowledge Base Structure

The RAG knowledge base should be organized into small documents, for example:

```text
knowledge/
  stride/
    spoofing.md
    tampering.md
    repudiation.md
    information-disclosure.md
    denial-of-service.md
    elevation-of-privilege.md
  components/
    api-gateway.md
    database.md
    storage.md
    identity-provider.md
    waf.md
    monitoring.md
```

Each document should include:

- Component or STRIDE category.
- Common threats.
- Evidence patterns.
- Countermeasures.
- Security references.

## Report Sections

Recommended final report:

1. Executive summary.
2. Architecture overview.
3. Components detected.
4. STRIDE coverage.
5. Prioritized threats.
6. Evidence per threat.
7. Countermeasures.
8. Risk score.
9. Human review checklist.
10. Limitations.

## LLM Prompt Contract

The LLM should receive:

- Architecture JSON.
- Detected components.
- Flows.
- Retrieved RAG context.
- Threat candidates from the STRIDE rule engine.

The LLM should output:

- Executive summary.
- Technical threat table.
- Prioritized remediation plan.
- Items requiring human validation.

## Validation Layer

The validator should check:

- Did the report mention components not present in JSON?
- Did it include threats for high-risk components?
- Did it cover all relevant STRIDE categories?
- Did every threat include countermeasures?
- Did it mark uncertainty when confidence is low?

If validation fails:

- Regenerate the report.
- Or mark the item as requiring human review.

## No-Hallucination Rule

The generative layer must not introduce components or flows that were not detected or manually confirmed.

Allowed wording:

```text
No explicit backup component was detected. Confirm if backup exists outside the diagram.
```

Avoid:

```text
The architecture has no backup.
```

This distinction is important for security accuracy.
