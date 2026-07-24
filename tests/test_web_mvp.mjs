import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import {
  backendPresentation,
  bboxToPercent,
  buildApiUrl,
  errorMessageForStatus,
  filterThreats,
  groupThreats,
  safeTechnicalDetails,
  summarizeAnalysis,
  validateAnalysisQuality,
  validateAnalysisResponse,
  validateImageFile,
} from "../app/ui-contract.mjs";

const html = readFileSync(new URL("../app/index.html", import.meta.url), "utf8");
const main = readFileSync(new URL("../app/main.js", import.meta.url), "utf8");
const css = readFileSync(new URL("../app/styles.css", import.meta.url), "utf8");
const server = readFileSync(new URL("../server.mjs", import.meta.url), "utf8");

const analysis = {
  analysisQuality: {
    status: "reliable",
    score: 1,
    reasons: [],
    recommendedAction: "Review before final approval.",
  },
  architecture: {
    flowStrategy: "legacy",
    components: [{ id: "api", name: "API", bbox: [10, 20, 110, 120] }],
    flows: [{ id: "f1", from: "api", to: "db" }],
  },
  threats: [
    { id: "t1", stride: "Spoofing", severity: "Critical", componentId: "api", countermeasures: ["MFA"] },
    { id: "t2", stride: "Tampering", severity: "High", componentId: "db", countermeasures: ["MFA", "TLS"] },
  ],
  audit: { analysisId: "analysis-1", pipelineVersion: "1.0.0-mvp" },
  pipeline: { flowStrategy: "legacy", flowStrategyTrace: { actionCounts: { keep: 1 } } },
};

test("1. initial render exposes upload and keeps results hidden", () => {
  assert.match(html, /id="dropZone"/);
  assert.match(html, /id="resultsRegion" hidden/);
});

test("2. health check uses the configured API base", () => {
  assert.equal(buildApiUrl("/api", "health"), "/api/health");
  assert.match(main, /buildApiUrl\(API_BASE_URL, "health"\)/);
});

test("3. unavailable backend has an honest status", () => {
  assert.equal(backendPresentation(null).backendLabel, "Backend indisponível");
});

test("4. supported image selection is valid", () => {
  assert.equal(validateImageFile({ type: "image/png", size: 1024 }).valid, true);
});

test("5. preview uses a local object URL", () => {
  assert.match(main, /URL\.createObjectURL\(file\)/);
  assert.match(main, /previewImage\.src = state\.previewUrl/);
});

test("6. removing a file clears selection and preview", () => {
  assert.match(main, /removeFileBtn\.addEventListener\("click", clearFile\)/);
  assert.match(main, /previewImage\.removeAttribute\("src"\)/);
});

test("7. invalid formats and oversized files are rejected", () => {
  assert.equal(validateImageFile({ type: "text/plain", size: 30 }).reason, "type");
  assert.equal(validateImageFile({ type: "image/jpeg", size: 26 * 1024 * 1024 }).reason, "size");
});

test("8. analysis submits multipart to analyze/full", () => {
  assert.match(main, /formData\.append\("image"/);
  assert.match(main, /buildApiUrl\(API_BASE_URL, "analyze\/full"\)/);
});

test("9. loading is explicit and duplicate submissions are blocked", () => {
  assert.match(html, /id="processingPanel"/);
  assert.match(main, /if \(state\.busy\) return/);
});

test("10. complete API responses are accepted and summarized", () => {
  assert.equal(validateAnalysisResponse(analysis), true);
  assert.deepEqual(summarizeAnalysis(analysis), {
    components: 1,
    flows: 1,
    threats: 2,
    critical: 1,
    vulnerabilities: 2,
    countermeasures: 2,
  });
  assert.match(main, /score\?\.value/);
});

test("11. partially empty arrays remain valid", () => {
  const empty = {
    architecture: { components: [], flows: [] },
    threats: [],
    analysisQuality: analysis.analysisQuality,
  };
  assert.equal(validateAnalysisResponse(empty), true);
  assert.equal(summarizeAnalysis(empty).threats, 0);
});

test("12. HTTP 415 has a safe, actionable message", () => {
  assert.match(errorMessageForStatus(415), /formato/i);
});

test("13. HTTP 500 does not expose internal details", () => {
  const message = errorMessageForStatus(500, "E:\\secret\\stack.py");
  assert.doesNotMatch(message, /secret|stack\.py/i);
});

test("14. components have a dedicated result table", () => {
  assert.match(html, /id="componentsBody"/);
  assert.match(main, /function renderComponents/);
});

test("15. flows have a dedicated result table", () => {
  assert.match(html, /id="flowsBody"/);
  assert.match(main, /function renderFlows/);
});

test("16. threats are grouped by STRIDE category", () => {
  const groups = groupThreats(analysis.threats);
  assert.equal(groups.get("Spoofing").length, 1);
  assert.equal(groups.get("Tampering").length, 1);
});

test("17. threat filters combine category, severity, and component", () => {
  assert.equal(filterThreats(analysis.threats, { stride: "Spoofing", severity: "Critical", component: "api" }).length, 1);
  assert.equal(filterThreats(analysis.threats, { component: "db" }).length, 1);
});

test("18. vulnerabilities and countermeasures use API threat data", () => {
  assert.match(html, /id="vulnerabilitiesBody"/);
  assert.match(main, /threat\.countermeasures/);
});

test("19. the active stable strategy is identified", () => {
  const status = backendPresentation({ status: "ok", flowStrategy: "legacy" });
  assert.match(status.strategyLabel, /estável: legacy/);
});

test("20. the controlled strategy receives an experimental badge", () => {
  const status = backendPresentation({ status: "ok", flowStrategy: "junction_aware_controlled" });
  assert.equal(status.experimental, true);
  assert.match(main, /experimental-badge/);
});

test("21. JSON export serializes the complete analysis", () => {
  assert.match(main, /JSON\.stringify\(state\.analysis, null, 2\)/);
  assert.match(main, /application\/json/);
});

test("22. browser printing and print layout are available", () => {
  assert.match(main, /window\.print\(\)/);
  assert.match(css, /@media print/);
});

test("23. basic keyboard and screen reader contracts exist", () => {
  assert.match(html, /class="skip-link"/);
  assert.match(html, /aria-live="polite"/);
  assert.match(html, /role="button"/);
  assert.match(main, /event\.key === "Enter" \|\| event\.key === " "/);
});

test("24. technical details omit local paths and internal model traces", () => {
  const details = safeTechnicalDetails({
    ...analysis,
    pipeline: {
      flowStrategy: "legacy",
      detectorModel: "E:\\models\\best.pt",
      flowStrategyTrace: { actionCounts: { keep: 1 }, sourcePath: "E:\\private\\x.json" },
    },
  });
  assert.doesNotMatch(JSON.stringify(details), /E:\\\\|detectorModel|sourcePath/);
});

test("25. frontend never attempts to change FLOW_STRATEGY", () => {
  assert.doesNotMatch(main, /FLOW_STRATEGY/);
  assert.doesNotMatch(html, /FLOW_STRATEGY/);
  assert.doesNotMatch(main, /junction_aware_controlled.*fetch|fetch.*junction_aware_controlled/s);
});

test("26. bbox conversion preserves the image coordinate ratio", () => {
  assert.deepEqual(bboxToPercent([100, 50, 300, 150], 1000, 500), {
    left: 10,
    top: 10,
    width: 20,
    height: 20,
  });
  assert.equal(bboxToPercent([100, 50, 1200, 150], 1000, 500), null);
  assert.match(main, /imageRect\.left - stageRect\.left/);
  assert.match(main, /componentOverlay\.style\.width/);
});

test("27. API base URL is injected at runtime without a fixed production host", () => {
  assert.match(server, /FRONTEND_API_BASE_URL/);
  assert.doesNotMatch(main, /https?:\/\//);
});

test("28. malformed analysis responses fail closed", () => {
  assert.equal(validateAnalysisResponse({ architecture: {}, threats: null }), false);
  assert.equal(validateAnalysisResponse(null), false);
});

test("29. quality contract is fail-closed and accepts all supported statuses", () => {
  assert.equal(validateAnalysisQuality(analysis.analysisQuality), true);
  assert.equal(validateAnalysisQuality({ ...analysis.analysisQuality, status: "review_required", score: 0.7 }), true);
  assert.equal(validateAnalysisQuality({ ...analysis.analysisQuality, status: "rejected", score: 0.2 }), true);
  assert.equal(validateAnalysisQuality({ ...analysis.analysisQuality, score: 1.1 }), false);
  assert.equal(validateAnalysisResponse({ architecture: { components: [], flows: [] }, threats: [] }), false);
});

test("30. rejected analyses suppress threats, mitigation, risk, and printing", () => {
  assert.match(html, /id="qualityPanel"/);
  assert.match(html, /id="threatsSection"/);
  assert.match(html, /id="mitigationSection"/);
  assert.match(main, /quality\.status === "rejected"/);
  assert.match(main, /elements\.threatsSection\.hidden = rejected/);
  assert.match(main, /elements\.printBtn\.disabled = rejected/);
  assert.match(main, /Risco não calculado/);
});
