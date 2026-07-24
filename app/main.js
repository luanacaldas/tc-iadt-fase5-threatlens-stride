import {
  STRIDE_CATEGORIES,
  backendPresentation,
  bboxToPercent,
  buildApiUrl,
  errorMessageForStatus,
  filterThreats,
  formatConfidence,
  groupThreats,
  safeTechnicalDetails,
  summarizeAnalysis,
  validateAnalysisResponse,
  validateImageFile,
} from "./ui-contract.mjs";

const config = window.__THREATLENS_CONFIG__ || { apiBaseUrl: "/api" };
const API_BASE_URL = config.apiBaseUrl || "/api";
const ANALYSIS_TIMEOUT_MS = 120_000;
const samples = [
  { name: "API simples", file: "01-simple-api.jpg", description: "Fluxo cliente, API e banco de dados" },
  { name: "Componentes mistos", file: "02-mixed-components.jpg", description: "Arquitetura genérica com múltiplos serviços" },
  { name: "Controles de segurança", file: "03-security-controls.jpg", description: "Arquitetura com controles explícitos" },
  { name: "Pipeline denso", file: "04-dense-pipeline.jpg", description: "Conectividade densa para demonstração" },
];

const byId = (id) => document.getElementById(id);
const elements = Object.fromEntries([
  "backendStatus", "strategyStatus", "dropZone", "chooseFileBtn", "imageInput", "fileSummary",
  "fileName", "fileSize", "replaceFileBtn", "removeFileBtn", "analyzeBtn", "previewFigure",
  "previewImage", "processingPanel", "processingSteps", "errorPanel", "errorMessage", "retryBtn",
  "sampleGrid", "resultsRegion", "downloadJsonBtn", "printBtn", "componentCount", "flowCount",
  "threatCount", "criticalCount", "vulnerabilityCount", "countermeasureCount", "riskBadge",
  "riskSummary", "analyzedStage", "analyzedImage", "componentOverlay", "diagramNotice",
  "componentsBody", "flowsBody", "alternativesSection", "alternativeReviewBody", "strideFilter",
  "severityFilter", "componentFilter", "clearFiltersBtn", "filterResult", "threatGroups",
  "vulnerabilitiesBody", "technicalSummary", "strategyDecisionSummary", "strategyTrace",
  "qualityPanel", "qualityStatus", "qualityScore", "qualityReasons", "qualityAction",
  "threatsSection", "mitigationSection",
].map((id) => [id, byId(id)]));

const state = {
  file: null,
  previewUrl: "",
  analysis: null,
  health: null,
  busy: false,
  progressTimers: [],
};

document.addEventListener("DOMContentLoaded", initialize);

function initialize() {
  bindEvents();
  renderSamples();
  populateStrideFilter();
  checkHealth();
}

function bindEvents() {
  elements.chooseFileBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    elements.imageInput.click();
  });
  elements.replaceFileBtn.addEventListener("click", () => elements.imageInput.click());
  elements.removeFileBtn.addEventListener("click", clearFile);
  elements.imageInput.addEventListener("change", () => selectFile(elements.imageInput.files?.[0]));
  elements.dropZone.addEventListener("click", (event) => {
    if (event.target === elements.dropZone || !event.target.closest("button")) elements.imageInput.click();
  });
  elements.dropZone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      elements.imageInput.click();
    }
  });
  for (const eventName of ["dragenter", "dragover"]) {
    elements.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropZone.classList.add("is-dragging");
    });
  }
  for (const eventName of ["dragleave", "drop"]) {
    elements.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropZone.classList.remove("is-dragging");
    });
  }
  elements.dropZone.addEventListener("drop", (event) => selectFile(event.dataTransfer?.files?.[0]));
  elements.analyzeBtn.addEventListener("click", analyzeSelectedFile);
  elements.retryBtn.addEventListener("click", analyzeSelectedFile);
  elements.downloadJsonBtn.addEventListener("click", downloadJson);
  elements.printBtn.addEventListener("click", () => window.print());
  for (const filter of [elements.strideFilter, elements.severityFilter, elements.componentFilter]) {
    filter.addEventListener("change", renderFilteredThreats);
  }
  elements.clearFiltersBtn.addEventListener("click", clearFilters);
  elements.analyzedImage.addEventListener("load", renderOverlay);
  window.addEventListener("beforeunload", revokePreviewUrl);
}

async function checkHealth() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8_000);
  try {
    const response = await fetch(buildApiUrl(API_BASE_URL, "health"), {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("health unavailable");
    state.health = await response.json();
    renderHealth(backendPresentation(state.health));
  } catch {
    state.health = null;
    renderHealth(backendPresentation(null));
  } finally {
    clearTimeout(timer);
  }
}

function renderHealth(presentation) {
  elements.backendStatus.className = `status-line ${presentation.available ? "available" : "unavailable"}`;
  elements.backendStatus.replaceChildren();
  const dot = document.createElement("span");
  dot.className = "status-dot";
  dot.setAttribute("aria-hidden", "true");
  elements.backendStatus.append(dot, document.createTextNode(presentation.backendLabel));
  elements.strategyStatus.replaceChildren(document.createTextNode(presentation.strategyLabel));
  if (presentation.experimental) {
    const badge = document.createElement("span");
    badge.className = "experimental-badge";
    badge.textContent = "Experimental";
    elements.strategyStatus.append(" ", badge);
  }
}

function renderSamples() {
  const fragment = document.createDocumentFragment();
  for (const sample of samples) {
    const article = document.createElement("article");
    article.className = "sample-card";
    const image = document.createElement("img");
    image.src = `/data/sample-diagrams/${sample.file}`;
    image.alt = `Diagrama de exemplo: ${sample.name}`;
    image.loading = "lazy";
    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = sample.name;
    const description = document.createElement("span");
    description.textContent = sample.description;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary-command";
    button.textContent = "Usar exemplo";
    button.addEventListener("click", () => selectSample(sample, button));
    body.append(title, description, button);
    article.append(image, body);
    fragment.append(article);
  }
  elements.sampleGrid.replaceChildren(fragment);
}

async function selectSample(sample, button) {
  hideError();
  const previousLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Carregando";
  try {
    const response = await fetch(`/data/sample-diagrams/${sample.file}`);
    if (!response.ok) throw new Error("sample unavailable");
    const blob = await response.blob();
    selectFile(new File([blob], sample.file, { type: blob.type || "image/jpeg" }));
    elements.dropZone.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch {
    showError("Não foi possível carregar este exemplo. Tente selecionar o arquivo manualmente.", false);
  } finally {
    button.disabled = false;
    button.textContent = previousLabel;
  }
}

function selectFile(file) {
  hideError();
  const validation = validateImageFile(file);
  if (!validation.valid) {
    showError(validation.message, false);
    clearFile({ keepError: true });
    return;
  }
  revokePreviewUrl();
  state.file = file;
  state.previewUrl = URL.createObjectURL(file);
  elements.previewImage.src = state.previewUrl;
  elements.fileName.textContent = file.name;
  elements.fileSize.textContent = formatBytes(file.size);
  elements.fileSummary.hidden = false;
  elements.previewFigure.hidden = false;
  elements.analyzeBtn.disabled = false;
  elements.imageInput.value = "";
}

function clearFile(options = {}) {
  revokePreviewUrl();
  state.file = null;
  elements.imageInput.value = "";
  elements.previewImage.removeAttribute("src");
  elements.fileSummary.hidden = true;
  elements.previewFigure.hidden = true;
  elements.analyzeBtn.disabled = true;
  if (!options.keepError) hideError();
}

function revokePreviewUrl() {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = "";
}

async function analyzeSelectedFile() {
  if (state.busy) return;
  const validation = validateImageFile(state.file);
  if (!validation.valid) {
    showError(validation.message, false);
    return;
  }
  state.busy = true;
  setBusy(true);
  hideError();
  startEstimatedProgress();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), ANALYSIS_TIMEOUT_MS);
  try {
    const formData = new FormData();
    formData.append("image", state.file, state.file.name);
    const response = await fetch(buildApiUrl(API_BASE_URL, "analyze/full"), {
      method: "POST",
      body: formData,
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    if (!response.ok) throw new ApiError(response.status, payload?.detail || "");
    if (!validateAnalysisResponse(payload)) throw new InvalidResponseError();
    state.analysis = payload;
    completeProgress();
    renderAnalysis(payload);
    elements.resultsRegion.hidden = false;
    elements.resultsRegion.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    const message = error.name === "AbortError"
      ? "A análise excedeu o tempo limite. Verifique o backend e tente novamente."
      : error instanceof ApiError
        ? errorMessageForStatus(error.status, error.detail)
        : error instanceof InvalidResponseError
          ? "O backend retornou uma resposta incompleta ou inválida."
          : "Não foi possível acessar o backend. Verifique se o serviço está em execução.";
    showError(message, true);
  } finally {
    clearTimeout(timeout);
    stopProgress();
    state.busy = false;
    setBusy(false);
  }
}

class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

class InvalidResponseError extends Error {}

function setBusy(busy) {
  elements.analyzeBtn.disabled = busy || !state.file;
  elements.chooseFileBtn.disabled = busy;
  elements.replaceFileBtn.disabled = busy;
  elements.removeFileBtn.disabled = busy;
  elements.processingPanel.hidden = !busy;
  elements.dropZone.setAttribute("aria-disabled", String(busy));
  elements.analyzeBtn.textContent = busy ? "Analisando arquitetura" : "Analisar arquitetura";
}

function startEstimatedProgress() {
  stopProgress();
  const steps = [...elements.processingSteps.querySelectorAll("li")];
  steps.forEach((step) => step.classList.remove("active", "complete"));
  const delays = [0, 900, 2_200, 4_000, 6_500];
  delays.forEach((delay, index) => {
    state.progressTimers.push(setTimeout(() => {
      steps.forEach((step, stepIndex) => {
        step.classList.toggle("complete", stepIndex < index);
        step.classList.toggle("active", stepIndex === index);
      });
    }, delay));
  });
}

function completeProgress() {
  [...elements.processingSteps.querySelectorAll("li")].forEach((step) => {
    step.classList.remove("active");
    step.classList.add("complete");
  });
}

function stopProgress() {
  state.progressTimers.forEach(clearTimeout);
  state.progressTimers = [];
}

function renderAnalysis(payload) {
  const architecture = payload.architecture;
  const components = architecture.components || [];
  const flows = architecture.flows || [];
  const alternatives = architecture.detectionAlternatives || [];
  renderSummary(payload);
  renderQuality(payload.analysisQuality);
  renderAnalyzedImage();
  renderComponents(components);
  renderFlows(flows, components);
  renderAlternatives(alternatives);
  populateThreatFilters(payload.threats, components);
  renderFilteredThreats();
  renderVulnerabilities(payload.threats);
  renderTechnicalDetails(payload);
}

function renderQuality(quality) {
  const labels = {
    reliable: "Estrutura confiável",
    review_required: "Revisão estrutural necessária",
    rejected: "Análise estrutural rejeitada",
  };
  elements.qualityPanel.className = `quality-panel quality-${quality.status}`;
  elements.qualityStatus.textContent = labels[quality.status];
  elements.qualityScore.textContent = `Qualidade ${Math.round(quality.score * 100)}%`;
  elements.qualityReasons.replaceChildren();
  const reasons = quality.reasons || [];
  if (!reasons.length) {
    const item = document.createElement("li");
    item.textContent = "Nenhuma inconsistência estrutural relevante foi detectada.";
    elements.qualityReasons.append(item);
  } else {
    for (const reason of reasons) {
      const item = document.createElement("li");
      item.textContent = typeof reason === "string" ? reason : reason.message;
      elements.qualityReasons.append(item);
    }
  }
  elements.qualityAction.textContent = quality.recommendedAction;

  const rejected = quality.status === "rejected";
  elements.threatsSection.hidden = rejected;
  elements.mitigationSection.hidden = rejected;
  elements.printBtn.disabled = rejected;
  elements.printBtn.title = rejected ? "O relatório foi suprimido pelo gate de qualidade." : "";
  if (rejected) {
    elements.riskBadge.textContent = "Risco não calculado";
    elements.riskSummary.textContent = "O relatório foi suprimido porque a arquitetura reconstruída é inconsistente.";
  }
}

function renderSummary(payload) {
  const summary = summarizeAnalysis(payload);
  elements.componentCount.textContent = summary.components;
  elements.flowCount.textContent = summary.flows;
  elements.threatCount.textContent = summary.threats;
  elements.criticalCount.textContent = summary.critical;
  elements.vulnerabilityCount.textContent = summary.vulnerabilities;
  elements.countermeasureCount.textContent = summary.countermeasures;
  const score = payload.score;
  const scoreValue = typeof score === "number" ? score : Number(score?.value ?? score?.overall ?? score?.riskScore);
  if (Number.isFinite(scoreValue)) {
    elements.riskBadge.textContent = score?.label
      ? `Risco ${score.label} (${scoreValue}/10)`
      : `Risco ${scoreValue}`;
    elements.riskSummary.textContent = score?.summary || "Pontuação consolidada retornada pelo motor de análise.";
  } else {
    elements.riskBadge.textContent = "Risco não informado";
    elements.riskSummary.textContent = "A API não retornou uma pontuação numérica consolidada.";
  }
}

function renderAnalyzedImage() {
  elements.componentOverlay.replaceChildren();
  elements.analyzedImage.src = state.previewUrl;
  elements.diagramNotice.textContent = "As sobreposições não alteram a imagem nem os dados recebidos.";
  if (elements.analyzedImage.complete) renderOverlay();
}

function renderOverlay() {
  elements.componentOverlay.replaceChildren();
  if (!state.analysis || !elements.analyzedImage.naturalWidth) return;
  const stageRect = elements.analyzedStage.getBoundingClientRect();
  const imageRect = elements.analyzedImage.getBoundingClientRect();
  elements.componentOverlay.style.left = `${imageRect.left - stageRect.left}px`;
  elements.componentOverlay.style.top = `${imageRect.top - stageRect.top}px`;
  elements.componentOverlay.style.width = `${imageRect.width}px`;
  elements.componentOverlay.style.height = `${imageRect.height}px`;
  let rendered = 0;
  for (const component of state.analysis.architecture.components || []) {
    const box = bboxToPercent(component.bbox, elements.analyzedImage.naturalWidth, elements.analyzedImage.naturalHeight);
    if (!box) continue;
    const marker = document.createElement("span");
    marker.className = `component-box ${component.reviewStatus === "pending" ? "needs-review" : ""}`;
    marker.style.left = `${box.left}%`;
    marker.style.top = `${box.top}%`;
    marker.style.width = `${box.width}%`;
    marker.style.height = `${box.height}%`;
    marker.title = component.name || component.id;
    elements.componentOverlay.append(marker);
    rendered += 1;
  }
  elements.diagramNotice.textContent = rendered
    ? `${rendered} componente(s) com coordenadas válidas foram localizados.`
    : "A API não retornou coordenadas suficientes; somente a imagem original é exibida.";
}

function renderComponents(components) {
  elements.componentsBody.replaceChildren();
  if (!components.length) return appendEmptyRow(elements.componentsBody, 5, "Nenhum componente foi identificado.");
  for (const component of components) {
    const row = document.createElement("tr");
    appendCells(row, [
      component.name || component.id || "Sem identificação",
      component.type || "Não informado",
      component.provider || "Não informado",
      formatConfidence(component.confidence),
      statusLabel(component.reviewStatus),
    ]);
    elements.componentsBody.append(row);
  }
}

function renderFlows(flows, components) {
  const names = new Map(components.map((item) => [item.id, item.name || item.id]));
  elements.flowsBody.replaceChildren();
  if (!flows.length) return appendEmptyRow(elements.flowsBody, 6, "Nenhum fluxo foi identificado.");
  for (const flow of flows) {
    const row = document.createElement("tr");
    appendCells(row, [
      names.get(flow.from) || flow.from || "Não informado",
      names.get(flow.to) || flow.to || "Não informado",
      `${names.get(flow.from) || flow.from || "?"} → ${names.get(flow.to) || flow.to || "?"}`,
      flow.protocol || "Não informado",
      formatConfidence(flow.confidence),
      flow.reviewStatus ? statusLabel(flow.reviewStatus) : flow.inferred ? "Revisão recomendada" : "Não informada",
    ]);
    elements.flowsBody.append(row);
  }
}

function renderAlternatives(alternatives) {
  elements.alternativeReviewBody.replaceChildren();
  elements.alternativesSection.hidden = !alternatives.length;
  for (const alternative of alternatives) {
    const row = document.createElement("tr");
    appendCells(row, [
      alternative.id,
      alternative.name || "Não informada",
      alternative.type || "Não informado",
      alternative.provider || "Não informado",
      formatConfidence(alternative.confidence),
      alternative.supersededBy || alternative.metadata?.supersededBy || "Não informado",
    ]);
    elements.alternativeReviewBody.append(row);
  }
}

function populateStrideFilter() {
  for (const category of STRIDE_CATEGORIES) appendOption(elements.strideFilter, category, category);
}

function populateThreatFilters(threats, components) {
  resetSelect(elements.severityFilter, "Todas");
  resetSelect(elements.componentFilter, "Todos");
  const severities = [...new Set(threats.map((item) => item.severity).filter(Boolean))].sort();
  severities.forEach((value) => appendOption(elements.severityFilter, value, value));
  components.forEach((component) => appendOption(elements.componentFilter, component.id, component.name || component.id));
}

function renderFilteredThreats() {
  const threats = filterThreats(state.analysis?.threats || [], {
    stride: elements.strideFilter.value,
    severity: elements.severityFilter.value,
    component: elements.componentFilter.value,
  });
  elements.filterResult.textContent = `${threats.length} ameaça(s) exibida(s).`;
  elements.threatGroups.replaceChildren();
  if (!threats.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Nenhuma ameaça corresponde aos filtros selecionados.";
    elements.threatGroups.append(empty);
    return;
  }
  for (const [category, items] of groupThreats(threats)) {
    if (!items.length) continue;
    const section = document.createElement("section");
    section.className = "threat-group";
    const heading = document.createElement("div");
    heading.className = "threat-group-heading";
    const title = document.createElement("h3");
    title.textContent = strideLabel(category);
    const count = document.createElement("span");
    count.textContent = String(items.length);
    heading.append(title, count);
    const list = document.createElement("div");
    list.className = "threat-list";
    items.forEach((threat) => list.append(renderThreat(threat)));
    section.append(heading, list);
    elements.threatGroups.append(section);
  }
}

function renderThreat(threat) {
  const article = document.createElement("article");
  article.className = "threat-item";
  const header = document.createElement("div");
  header.className = "threat-item-header";
  const title = document.createElement("h4");
  title.textContent = threat.title || "Ameaça sem título";
  const severity = document.createElement("span");
  severity.className = `severity severity-${String(threat.severity || "unknown").toLowerCase()}`;
  severity.textContent = threat.severity || "Não informada";
  header.append(title, severity);
  article.append(header);
  appendFact(article, "Ativo afetado", threat.componentName || threat.componentId);
  appendFact(article, "Evidência / vulnerabilidade", threat.evidence);
  if (Array.isArray(threat.countermeasures) && threat.countermeasures.length) {
    const block = document.createElement("div");
    block.className = "countermeasure-block";
    const label = document.createElement("strong");
    label.textContent = "Contramedidas";
    const list = document.createElement("ul");
    threat.countermeasures.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      list.append(li);
    });
    block.append(label, list);
    article.append(block);
  }
  return article;
}

function renderVulnerabilities(threats) {
  elements.vulnerabilitiesBody.replaceChildren();
  if (!threats.length) {
    appendEmptyRow(elements.vulnerabilitiesBody, 4, "Nenhuma vulnerabilidade adicional foi retornada para esta análise.");
    return;
  }
  for (const threat of threats) {
    const row = document.createElement("tr");
    appendCells(row, [
      threat.title || threat.evidence || "Não informada",
      threat.componentName || threat.componentId || "Arquitetura",
      threat.severity || "Não informada",
      Array.isArray(threat.countermeasures) && threat.countermeasures.length
        ? threat.countermeasures.join(" • ")
        : "Nenhuma contramedida retornada",
    ]);
    elements.vulnerabilitiesBody.append(row);
  }
}

function renderTechnicalDetails(payload) {
  const details = safeTechnicalDetails(payload, state.health || {});
  elements.technicalSummary.replaceChildren();
  for (const [label, value] of Object.entries(details.summary)) {
    if (value === undefined || value === null || value === "") continue;
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    elements.technicalSummary.append(dt, dd);
  }
  elements.strategyDecisionSummary.replaceChildren();
  const actions = Object.entries(details.actionCounts);
  if (actions.length) {
    const heading = document.createElement("strong");
    heading.textContent = "Decisões da estratégia";
    const list = document.createElement("ul");
    for (const [action, count] of actions) {
      const item = document.createElement("li");
      item.textContent = `${action}: ${count}`;
      list.append(item);
    }
    elements.strategyDecisionSummary.append(heading, list);
  }
  elements.strategyTrace.textContent = Object.keys(details.trace).length
    ? JSON.stringify(details.trace, null, 2)
    : "Nenhum flowStrategyTrace foi retornado.";
}

function clearFilters() {
  elements.strideFilter.value = "";
  elements.severityFilter.value = "";
  elements.componentFilter.value = "";
  renderFilteredThreats();
}

function downloadJson() {
  if (!state.analysis) return;
  const blob = new Blob([JSON.stringify(state.analysis, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `threatlens-${state.analysis.audit?.analysisId || "analysis"}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function showError(message, retryAvailable) {
  elements.errorMessage.textContent = message;
  elements.retryBtn.hidden = !retryAvailable;
  elements.errorPanel.hidden = false;
}

function hideError() {
  elements.errorPanel.hidden = true;
  elements.errorMessage.textContent = "";
}

function appendCells(row, values) {
  values.forEach((value) => {
    const cell = document.createElement("td");
    cell.textContent = value ?? "Não informado";
    row.append(cell);
  });
}

function appendEmptyRow(body, columns, message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = columns;
  cell.className = "empty-cell";
  cell.textContent = message;
  row.append(cell);
  body.append(row);
}

function appendFact(parent, label, value) {
  if (!value) return;
  const paragraph = document.createElement("p");
  const strong = document.createElement("strong");
  strong.textContent = `${label}: `;
  paragraph.append(strong, document.createTextNode(String(value)));
  parent.append(paragraph);
}

function appendOption(select, value, label) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  select.append(option);
}

function resetSelect(select, firstLabel) {
  select.replaceChildren();
  appendOption(select, "", firstLabel);
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusLabel(value) {
  const labels = { pending: "Revisão recomendada", confirmed: "Confirmado", auto_accepted: "Aceito automaticamente" };
  return labels[value] || value || "Não informado";
}

function strideLabel(value) {
  const labels = {
    Spoofing: "Spoofing (Falsificação)",
    Tampering: "Tampering (Adulteração)",
    Repudiation: "Repudiation (Repúdio)",
    "Information Disclosure": "Information Disclosure (Divulgação)",
    "Denial of Service": "Denial of Service (Negação de serviço)",
    "Elevation of Privilege": "Elevation of Privilege (Elevação de privilégio)",
  };
  return labels[value] || value;
}
