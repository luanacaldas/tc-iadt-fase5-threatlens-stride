export const MAX_IMAGE_BYTES = 25 * 1024 * 1024;
export const ACCEPTED_IMAGE_TYPES = Object.freeze(["image/png", "image/jpeg", "image/webp"]);
export const STRIDE_CATEGORIES = Object.freeze([
  "Spoofing",
  "Tampering",
  "Repudiation",
  "Information Disclosure",
  "Denial of Service",
  "Elevation of Privilege",
]);

const BLOCKED_TECHNICAL_KEYS = /(?:path|file|stack|secret|token|api.?key|detectorModel|modelTrace|structureTrace|ocrTrace)/i;
const ABSOLUTE_PATH = /(?:[A-Za-z]:\\|\\\\|\/(?:home|users|var|tmp|opt)\/)/i;

export function validateImageFile(file) {
  if (!file) return { valid: false, reason: "missing", message: "Selecione uma imagem antes de analisar." };
  if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
    return {
      valid: false,
      reason: "type",
      message: "O formato selecionado não é suportado. Use PNG, JPEG ou WebP.",
    };
  }
  if (!Number.isFinite(file.size) || file.size <= 0) {
    return { valid: false, reason: "empty", message: "O arquivo selecionado está vazio." };
  }
  if (file.size > MAX_IMAGE_BYTES) {
    return { valid: false, reason: "size", message: "A imagem excede o limite de 25 MB." };
  }
  return { valid: true, reason: null, message: "" };
}

export function buildApiUrl(baseUrl, path) {
  const base = String(baseUrl || "/api").replace(/\/+$/, "");
  const suffix = String(path || "").replace(/^\/+/, "");
  return `${base}/${suffix}`;
}

export function backendPresentation(health) {
  const available = health?.status === "ok";
  const strategy = health?.flowStrategy || health?.flowStrategies?.selected || "indisponível";
  const experimental = strategy === "junction_aware_controlled";
  return {
    available,
    strategy,
    experimental,
    backendLabel: available ? "Backend disponível" : "Backend indisponível",
    strategyLabel: experimental
      ? "Estratégia experimental: junction_aware_controlled"
      : strategy === "legacy"
        ? "Estratégia estável: legacy"
        : `Estratégia: ${strategy}`,
  };
}

export function validateAnalysisResponse(payload) {
  if (!payload || typeof payload !== "object") return false;
  if (!payload.architecture || typeof payload.architecture !== "object") return false;
  if (!Array.isArray(payload.threats)) return false;
  if (!validateAnalysisQuality(payload.analysisQuality)) return false;
  const { components = [], flows = [] } = payload.architecture;
  return Array.isArray(components) && Array.isArray(flows);
}

export function validateAnalysisQuality(quality) {
  if (!quality || typeof quality !== "object") return false;
  if (!["reliable", "review_required", "rejected"].includes(quality.status)) return false;
  if (!Number.isFinite(quality.score) || quality.score < 0 || quality.score > 1) return false;
  if (!Array.isArray(quality.reasons)) return false;
  if (typeof quality.recommendedAction !== "string" || !quality.recommendedAction.trim()) return false;
  return quality.reasons.every((reason) => (
    typeof reason === "string"
    || (reason && typeof reason === "object" && typeof reason.code === "string" && typeof reason.message === "string")
  ));
}

export function summarizeAnalysis(payload) {
  const architecture = payload?.architecture || {};
  const components = Array.isArray(architecture.components) ? architecture.components : [];
  const flows = Array.isArray(architecture.flows) ? architecture.flows : [];
  const threats = Array.isArray(payload?.threats) ? payload.threats : [];
  const countermeasures = new Set();
  for (const threat of threats) {
    for (const item of Array.isArray(threat.countermeasures) ? threat.countermeasures : []) {
      if (typeof item === "string" && item.trim()) countermeasures.add(item.trim());
    }
  }
  return {
    components: components.length,
    flows: flows.length,
    threats: threats.length,
    critical: threats.filter((item) => String(item.severity).toLowerCase() === "critical").length,
    vulnerabilities: threats.length,
    countermeasures: countermeasures.size,
  };
}

export function groupThreats(threats) {
  const groups = new Map(STRIDE_CATEGORIES.map((category) => [category, []]));
  for (const threat of Array.isArray(threats) ? threats : []) {
    const category = groups.has(threat.stride) ? threat.stride : "Outras";
    if (!groups.has(category)) groups.set(category, []);
    groups.get(category).push(threat);
  }
  return groups;
}

export function filterThreats(threats, filters = {}) {
  return (Array.isArray(threats) ? threats : []).filter((threat) => {
    if (filters.stride && threat.stride !== filters.stride) return false;
    if (filters.severity && threat.severity !== filters.severity) return false;
    if (filters.component && threat.componentId !== filters.component) return false;
    return true;
  });
}

export function bboxToPercent(bbox, naturalWidth, naturalHeight) {
  if (!Array.isArray(bbox) || bbox.length !== 4) return null;
  if (!(naturalWidth > 0) || !(naturalHeight > 0)) return null;
  const values = bbox.map(Number);
  if (values.some((value) => !Number.isFinite(value))) return null;
  const [x1, y1, x2, y2] = values;
  if (x1 < 0 || y1 < 0 || x2 <= x1 || y2 <= y1 || x2 > naturalWidth || y2 > naturalHeight) return null;
  return {
    left: (x1 / naturalWidth) * 100,
    top: (y1 / naturalHeight) * 100,
    width: ((x2 - x1) / naturalWidth) * 100,
    height: ((y2 - y1) / naturalHeight) * 100,
  };
}

function sanitizeTechnicalValue(value, depth = 0) {
  if (depth > 6) return "[resumo omitido]";
  if (Array.isArray(value)) return value.slice(0, 100).map((item) => sanitizeTechnicalValue(item, depth + 1));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !BLOCKED_TECHNICAL_KEYS.test(key))
        .map(([key, item]) => [key, sanitizeTechnicalValue(item, depth + 1)]),
    );
  }
  if (typeof value === "string" && ABSOLUTE_PATH.test(value)) return "[caminho local omitido]";
  return value;
}

export function safeTechnicalDetails(payload, health = {}) {
  const audit = payload?.audit || {};
  const pipeline = payload?.pipeline || {};
  const trace = sanitizeTechnicalValue(pipeline.flowStrategyTrace || {});
  return {
    summary: {
      "Estratégia utilizada": pipeline.flowStrategy || payload?.architecture?.flowStrategy || health.flowStrategy,
      "Status da estratégia": (pipeline.flowStrategy || health.flowStrategy) === "junction_aware_controlled"
        ? "Experimental"
        : "Estável",
      Versão: audit.pipelineVersion || health.version,
      "ID da análise": audit.analysisId,
      "ID da requisição": audit.requestId,
      "Gerado em": audit.generatedAt,
    },
    trace,
    actionCounts: trace?.actionCounts && typeof trace.actionCounts === "object" ? trace.actionCounts : {},
  };
}

export function errorMessageForStatus(status, detail = "") {
  const messages = {
    400: "A imagem está corrompida ou não pôde ser interpretada.",
    413: "A imagem excede o limite aceito pelo sistema.",
    415: "O formato enviado não é suportado. Escolha uma imagem aceita pelo sistema.",
    422: "A imagem não contém os dados necessários para concluir a análise.",
    500: "O backend encontrou um erro ao processar a arquitetura.",
    502: "O backend está indisponível. Verifique o serviço e tente novamente.",
    503: "O detector supervisionado está indisponível neste momento.",
  };
  return messages[status] || (detail ? "A solicitação não pôde ser concluída." : "Ocorreu um erro inesperado durante a análise.");
}

export function formatConfidence(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${Math.round(number * 100)}%` : "Não informada";
}
