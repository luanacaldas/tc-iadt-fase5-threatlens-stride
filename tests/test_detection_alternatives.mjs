import assert from "node:assert/strict";
import test from "node:test";

import { createHistoryEntry, serializeAnalysisJson } from "../src/analysis_artifacts.mjs";
import { analyzeArchitecture, normalizeArchitecture } from "../src/threatlens.mjs";

function architecture(withAlternatives = true) {
  const payload = {
    name: "JavaScript alternative round-trip",
    components: [
      { id: "api", name: "API", type: "api_gateway", provider: "aws", confidence: 0.9 },
      { id: "db", name: "DB", type: "database", provider: "aws", confidence: 0.88 }
    ],
    flows: [{ id: "flow_api_db", from: "api", to: "db", protocol: "TLS", confidence: 0.8 }]
  };
  if (withAlternatives) {
    payload.detectionAlternatives = [
      {
        id: "compute_superseded",
        name: "Compute hypothesis",
        type: "compute",
        provider: "aws",
        confidence: 0.61,
        bbox: [10, 10, 40, 40],
        metadata: {
          supersededBy: "api",
          supersededReason: "semantic_conflict",
          customEvidence: { source: "detector-v15" }
        }
      },
      {
        id: "storage_superseded",
        name: "Storage hypothesis",
        type: "storage",
        provider: "azure",
        confidence: 0.55,
        bbox: [50, 10, 80, 40],
        metadata: { supersededBy: "db", supersededReason: "shared_anchor" }
      }
    ];
  }
  return payload;
}

test("local normalizer preserves every alternative and reports zero loss", () => {
  const input = architecture();
  const normalized = normalizeArchitecture(input);

  assert.equal(normalized.detectionAlternatives.length, input.detectionAlternatives.length);
  assert.equal(normalized.detectionAlternativeTrace.alternativeLossCount, 0);
  assert.deepEqual(normalized.detectionAlternatives[0].metadata.customEvidence, { source: "detector-v15" });
});

test("alternatives do not change STRIDE threats, risk, nodes, or edges", () => {
  const withAlternatives = analyzeArchitecture(architecture());
  const withoutAlternatives = analyzeArchitecture(architecture(false));
  const alternativeIds = new Set(withAlternatives.architecture.detectionAlternatives.map((item) => item.id));

  assert.deepEqual(withAlternatives.threats, withoutAlternatives.threats);
  assert.deepEqual(withAlternatives.score, withoutAlternatives.score);
  assert.deepEqual(withAlternatives.coverage, withoutAlternatives.coverage);
  assert.deepEqual(withAlternatives.graph, withoutAlternatives.graph);
  assert.ok(withAlternatives.threats.every((threat) => !alternativeIds.has(threat.componentId)));
  assert.ok(withAlternatives.graph.nodes.every((node) => !alternativeIds.has(node.id)));
  assert.ok(withAlternatives.graph.edges.every((edge) => !alternativeIds.has(edge.from) && !alternativeIds.has(edge.to)));
});

test("history and JSON export preserve the exact alternative count", () => {
  const analysis = analyzeArchitecture(architecture());
  analysis.audit = { analysisId: "analysis-test", generatedAt: "2026-07-20T12:00:00Z" };

  const historyEntry = createHistoryEntry(analysis);
  const exported = JSON.parse(serializeAnalysisJson(analysis));

  assert.equal(historyEntry.analysis.architecture.detectionAlternatives.length, 2);
  assert.equal(exported.architecture.detectionAlternatives.length, 2);
  assert.notEqual(historyEntry.analysis, analysis);
});

test("Markdown export lists every alternative as review-only", () => {
  const analysis = analyzeArchitecture(architecture());

  assert.match(analysis.reportMarkdown, /Detection alternatives pending review/);
  assert.match(analysis.reportMarkdown, /compute_superseded/);
  assert.match(analysis.reportMarkdown, /storage_superseded/);
  assert.match(analysis.reportMarkdown, /excluded from the architecture graph, STRIDE analysis, and risk calculation/);
});

test("old payloads without alternatives remain compatible", () => {
  const analysis = analyzeArchitecture(architecture(false));

  assert.deepEqual(analysis.architecture.detectionAlternatives, []);
  assert.deepEqual(analysis.architecture.detectionAlternativeTrace, {
    inputCount: 0,
    outputCount: 0,
    alternativeLossCount: 0
  });
});
