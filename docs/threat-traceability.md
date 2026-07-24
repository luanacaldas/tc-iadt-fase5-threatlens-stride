# Threat Traceability

## Contract

Every threat returned by the API includes an `evidenceTrace` object with:

- `ruleId` and `ruleSource` for the deterministic decision.
- `componentIds` involved in the finding.
- `flowIds` that satisfy an architecture-level rule.
- `boundaryIds` crossed by those supporting flows.
- `absenceEvidence` for missing-control rules.
- `ragSourceIds` linked to a response-level evidence catalog.

The `evidenceCatalog` contains stable SHA-256-derived IDs, source paths, sections, and short
excerpts from the local knowledge base. The dashboard resolves these IDs inside each threat
card without duplicating complete RAG documents in every item.

## Retrieval Strategy

ThreatLens performs one local vector retrieval per analysis. Its audit `top-k` grows with the
number of distinct component types and covered STRIDE categories, capped at 18 chunks. Sources
are associated with threats only when their component or STRIDE path is relevant; retrieval
alone is not presented as proof that a source supports every finding.

## Verification

On the sample architecture, the API returned:

- 17 threats with trace objects (17/17).
- 18 catalogued RAG chunks.
- 15 threats with directly related RAG sources.
- Explicit flow `f5` and components `compute,database` for the compute-to-database rule.

The browser renders a collapsed `Ver rastreabilidade` section on every visible threat card,
keeping the default report scannable while making the decision path inspectable.
