export function serializeAnalysisJson(analysis) {
  return JSON.stringify(analysis, null, 2);
}

export function createHistoryEntry(analysis) {
  return {
    id: analysis.audit?.analysisId ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    generatedAt: analysis.audit?.generatedAt ?? new Date().toISOString(),
    architectureName: analysis.architecture?.name ?? "Arquitetura sem nome",
    analysis: structuredClone(analysis)
  };
}
