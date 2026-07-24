# Limitações e uso responsável

- Diagramas densos: cruzamentos, linhas longas, cotovelos, bordas de grupos e conectores
  paralelos ainda podem produzir fluxos extras ou ausentes.
- Setas: arrowheads pequenos, borrados ou sobrepostos reduzem a confiança da direção.
- Endpoints: proximidade geométrica pode associar uma linha ao componente incorreto.
- `review_only`: sinais incompletos são apresentados para revisão e nunca bloqueados
  automaticamente pela estratégia controlada.
- Caso C04: a junção densa supervisionada exige proteção explícita e não sustenta uma
  regra geral de redirecionamento de endpoints.
- Revisão humana: componentes pendentes, conflitos OCR, fluxos inferidos, protocolos
  desconhecidos e fronteiras candidatas devem ser confirmados antes de decisões reais.
- Generalização: a estratégia controlada foi validada apenas em `development_tuning`;
  nenhum holdout foi executado em `DELIVERY-001`.
- Estratégia padrão: `junction_aware_controlled` é experimental e opt-in. `legacy`
  permanece padrão e reversível por configuração.
- Taxonomia: o detector cobre 14 classes canônicas; serviços fora dessas classes são
  aproximados, abstidos ou encaminhados para revisão.
- Segurança: o relatório modela ameaças, mas não substitui teste de invasão, revisão de
  configuração cloud, análise de código ou validação de controles em produção.
- RAG e LLM: o modo local é determinístico. Recursos remotos são opcionais, exigem
  configuração explícita e não devem receber diagramas confidenciais sem autorização.
