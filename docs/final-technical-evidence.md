# Evidencias Tecnicas Finais

## Escopo entregue

ThreatLens executa localmente o fluxo imagem -> componentes -> grafo -> revisao humana -> STRIDE
-> gestao de ameacas -> relatorio. O detector supervisionado e a fonte primaria; OCR semantico e
heuristicas estruturais apenas criam propostas pendentes de revisao. O motor STRIDE e deterministico
e usa uma base RAG local versionada, portanto o relatorio nao depende de uma LLM paga. A recuperacao
usa embeddings locais quando disponiveis e fallback lexical deterministico sobre as mesmas fontes.

## Evidencias quantitativas

| Evidencia | Resultado |
| --- | ---: |
| Detector registrado, teste hibrido | mAP50 0,9009; recall 0,8417 |
| Benchmark estrutural real, fluxos direcionados | F1 0,4225 |
| Benchmark estrutural real, protocolos | F1 0,8000 |
| Classificador supervisionado de arrowheads | F1 0,9747 em holdout gerado |
| Golden set STRIDE | F1 1,0000; cobertura 100% |
| Holdout cego ponta a ponta inicial | F1 de ameacas 0,0254 |
| Diagnostico pos-hoc legado com OCR conservador | F1 de ameacas 0,1325 |
| Desenvolvimento v7, contrato provider-aware | F1 0,4188; recall tipado 0,5056 |
| Desenvolvimento v12, ancora adaptativa e replica groups | F1 0,4723; recall tipado 0,5926 |
| Desenvolvimento v13, abstencao semantica auditavel | F1 0,5033; recall tipado 0,6176 |
| Desenvolvimento v15, arbitragem semantica espacial | F1 0,5296; precisao 0,4343; recall 0,6786 |
| Junction-aware controlado, desenvolvimento | 52 conexoes corretas; 75 falsos fluxos; 19 ausentes; recall 0,7324; F1 0,5253; acuracia de direcao 0,8654 |
| Quality gate estrutural | 0 verdadeiros positivos bloqueados; controles C01-C07 aprovados |
| Holdout prospectivo v12, primeira execucao selada | F1 0,3457; recall tipado 0,4225 |
| Pos-hoc atual, anotacoes FIAP originais | F1 0,2143 |
| Pos-hoc atual, anotacoes FIAP realinhadas | F1 0,3205; recall tipado 0,3109 |
| Pos-hoc v12, anotacoes FIAP realinhadas | F1 0,3104; recall tipado 0,2924 |
| FIAP AWS / FIAP Azure, pos-hoc | F1 0,5900 / 0,3256 |
| Calibracao leave-one-diagram-out | Brier 0,4414 -> 0,1639 |
| Erro esperado de calibracao | ECE 0,5335 -> 0,1347 |
| Testes automatizados | 350 aprovados |

Os 85 testes representam a baseline historica preservada pela TL-001. A suite atual possui 350
testes aprovados e inclui os contratos adicionados posteriormente, sem apagar essa evidencia.

O benchmark real possui 15 imagens verificadas manualmente: nove de desenvolvimento e seis cegas,
com AWS, Azure, GCP, estilos genericos e as duas figuras FIAP. Os arquivos registram hashes,
componentes, fluxos, direcao, protocolos e fronteiras.

O resultado cego inicial permanece imutavel como baseline historico. A v12 possui um segundo resultado
cego em tres grupos de origem ainda nao avaliados: benchmark, imagens, detector e resultado foram
selados por SHA-256 antes da primeira inferencia. As anotacoes foram produzidas por inspecao visual
assistida pelo Codex e ainda aguardam verificacao humana independente; essa proveniencia esta
registrada em `prospective-v12-provenance-erratum.json`. Depois da abertura
do holdout, a camada OCR passou a recompor rotulos verticais, adaptar a geometria para estilos com
rotulo abaixo do icone ou dentro de cartoes e propagar contexto explicito de provedor. A revisao
tambem revelou deslocamento sistematico nas caixas da figura FIAP AWS. O original foi preservado;
`benchmark-fiap-corrected-v3.json` registra hash do pai, justificativa e status pos-hoc. O comparativo
completo esta em `data/results/end-to-end-improvement-comparison.json`.

A v12 associa rotulos Azure a ancoras visuais acima, abaixo ou inline de forma adaptativa e agrupa
replicas adjacentes em um deployment group auditavel, preservando `instanceCount` e ids de origem.
No desenvolvimento, isso elevou o F1 de 0,4188 para 0,4723. Na primeira execucao do novo holdout,
o F1 foi 0,3457. A cadeia imutavel pode ser verificada com `npm.cmd run benchmark:prospective:audit`.

A v13 trata divergencias entre a classe YOLO e semantica OCR explicita por abstencao: a hipotese
supervisionada permanece em `detectionAlternatives`, mas nao gera ameacas automaticamente quando uma
proposta semantica conflitante e localizada esta disponivel. O F1 de desenvolvimento chegou a
0,5033. Nos dois benchmarks ja abertos, a v13 repetiu os resultados da v12 sem regressao; esses
replays permanecem classificados como pos-hoc.

A v15 adiciona arbitragem para interpretacoes semanticas que compartilham a mesma ancora visual e
para hipoteses YOLO conflitantes na mesma regiao. Evidencia do mesmo tipo protege a hipotese
supervisionada; as hipoteses suprimidas continuam em `detectionAlternatives`. No desenvolvimento,
o total de ameacas indevidas caiu de 228 para 198, mantendo 152 acertos e recall tipado 0,6176. O F1
subiu para 0,5296. Esse resultado orientou implementacao e nao e evidencia cega.

## Active learning e decisao de modelo

Nove imagens reais de desenvolvimento geraram anotacoes YOLO sem reutilizar os XMLs de augmentation
do Kaggle. Um fine-tuning curto de tres epocas produziu mAP50 0,9045 no teste hibrido, mas reduziu o
recall tipado real de 0,1528 para 0,1389. Pela regra definida antes da comparacao, o checkpoint foi
rejeitado e o modelo `threatlens-hybrid-v2` continuou registrado. O resultado negativo foi preservado
em `data/results/active-learning/model-comparison.json`.

## Calibracao, abstention e auditoria

A confianca bruta do YOLO e preservada, mas a decisao de aceitacao usa uma regressao logistica
calibrada com confianca e area relativa da caixa. A validacao leave-one-diagram-out usou somente os
nove diagramas de desenvolvimento. Nenhum limiar avaliado atingiu precisao de 80% com cobertura
util; portanto, o limiar operacional ficou em 0,90 e as deteccoes reais incertas seguem para revisao.
Essa abstencao e uma decisao de seguranca intencional, nao uma alegacao de autonomia inexistente.

`npm.cmd run benchmark:real:audit` verifica os 15 hashes, coordenadas, ids, endpoints, protocolos,
fronteiras, cobertura de provedores e vazamento para active learning. A auditoria atual passa sem
erros e confirma zero ids do holdout no conjunto de refinamento. A auditoria prospectiva verifica
mais tres imagens e a cadeia detector -> benchmark -> resultado. Permanece registrada a pendencia
de uma segunda pessoa anotadora independente.

## Produto e governanca

- Cada ameaca tem status aberta, mitigada, aceita ou falso positivo; responsavel, justificativa e contramedida.
- O dashboard compara risco inerente e residual e mantem historico local de versoes da arquitetura.
- As referencias CWE, CAPEC, OWASP e MITRE ATT&CK aparecem na rastreabilidade e no PDF.
- O PDF inclui sumario executivo, matriz de risco e plano priorizado de mitigacao.
- A pagina Limitacoes comunica dominio, incertezas estruturais, escopo semantico e limite do benchmark.
- JSON, Markdown, PDF e dashboard responsivo oferecem mais de duas formas de visualizacao.
- O quality gate classifica a reconstrucao como `reliable`, `review_required` ou `rejected`.
- Em `rejected`, ameacas, risco, contramedidas e PDF sao suprimidos para impedir que uma
  arquitetura inconsistente seja apresentada como analise confiavel.

## Reprodutibilidade

```bash
npm.cmd run repro:manifest
npm.cmd run verify
npm.cmd run report:sample-pdf
```

O manifesto registra seeds, versoes e SHA-256 dos modelos, datasets, codigo critico e resultados.
As dependencias do runtime Docker ficam travadas em `backend/requirements-lock.txt`. Durante o build,
o modelo de embeddings e os 100 trechos RAG sao incorporados a imagem; em execucao, as flags offline
do Hugging Face bloqueiam downloads tardios. Se o cache de embeddings estiver ausente, a recuperacao
lexical mantem o RAG local operacional e expoe `retrievalMode: lexical`. `GET /api/ready` somente retorna
200 quando detector, calibracao e algum modo RAG estao disponiveis. `npm.cmd run offline:package` constroi, inspeciona e exporta a
imagem autocontida com um manifesto SHA-256. Chamadas remotas e relatorios generativos permanecem
desativados por padrao.

## Limitacoes honestas

Os dois holdouts mostraram que bom desempenho em recortes de icones nao garante generalizacao para
diagramas completos. A camada semantica melhorou substancialmente o diagnostico, mas estilos cloud
ainda nao vistos, fronteiras de confianca e linhas densas continuam sendo os principais pontos
fracos. Por isso, deteccoes OCR, fluxos e fronteiras permanecem revisaveis e o sistema nao afirma que
ausencia de alerta equivale a ausencia de risco. O caminho de evolucao e ampliar o holdout
prospectivo, fazer dupla anotacao com adjudicacao e treinar componentes e relacionamentos com maior
diversidade.
