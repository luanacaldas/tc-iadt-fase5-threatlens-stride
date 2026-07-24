# Interface web do MVP

Versao: `1.0.0-mvp`  
Escopo: `WEB-MVP-001`

## Arquitetura

A interface e uma SPA sem framework e sem dependencias de runtime. O servidor Node em
`server.mjs` entrega os arquivos estaticos e encaminha `/api/*` ao FastAPI. Essa escolha
preserva a stack existente e mantem o pacote offline pequeno.

| Arquivo | Responsabilidade |
| --- | --- |
| `app/index.html` | estrutura semantica, regioes e estados vazios |
| `app/styles.css` | layout responsivo e folha de impressao |
| `app/main.js` | upload, chamada da API e renderizacao por DOM seguro |
| `app/ui-contract.mjs` | validacao, filtros, resumo, bbox e sanitizacao testaveis |
| `app/runtime-config.js` | fallback local para configuracao publica |
| `server.mjs` | arquivos estaticos, configuracao de runtime e proxy local |

## Fluxo e integracao

Ao iniciar, a SPA consulta `GET /health` e mostra disponibilidade, versao e estrategia.
A interface nunca altera `FLOW_STRATEGY`: `legacy` continua padrao e
`junction_aware_controlled` recebe o selo `Experimental` quando o backend foi iniciado
com essa configuracao.

Uma imagem somente e enviada depois do comando `Analisar arquitetura`. O frontend monta
`multipart/form-data` com o campo `image` e chama `POST /analyze/full`. A resposta real
alimenta todas as visualizacoes e a exportacao JSON. Nao existem resultados de exemplo
codificados no cliente.

`FRONTEND_API_BASE_URL` define a base da API e usa `/api` por padrao. O servidor injeta o
valor em `/app/runtime-config.js` com `Cache-Control: no-store`. Para origens distintas,
configure `ALLOWED_ORIGINS` no backend; nenhuma chave ou credencial deve ser colocada no
frontend.

## Componentes da experiencia

- upload por clique, teclado ou drag and drop, com preview e validacao local;
- quatro diagramas de demonstracao processados pela API;
- progresso estimado e bloqueio de submissao duplicada;
- resumo calculado a partir da resposta;
- imagem original e overlays somente para `bbox` validos;
- tabelas de componentes, fluxos e alternativas somente para revisao;
- ameacas agrupadas por STRIDE com filtros combinaveis;
- vulnerabilidades e contramedidas derivadas das ameacas retornadas;
- detalhes tecnicos allowlisted, sem caminhos locais ou traces internos;
- download do JSON completo e impressao pelo navegador.

## Loading e erros

As cinco fases visuais sao uma estimativa honesta enquanto uma unica requisicao esta em
andamento; nao representam telemetria do backend. O timeout e de 120 segundos. A camada
de contrato trata ausencia de arquivo, tipo, tamanho, respostas invalidas, indisponibilidade
e os codigos 400, 413, 415, 422, 500, 502 e 503 sem mostrar mensagens internas.

## Acessibilidade e responsividade

A pagina possui skip link, landmarks, hierarquia de titulos, `aria-live`, alerta de erro,
operacao do drop zone por Enter ou Espaco, foco visivel, contraste e suporte a
`prefers-reduced-motion`. As tabelas mantem rolagem horizontal, e os grids sao reduzidos
para uma coluna em telas estreitas.

## Execucao e testes

```powershell
npm.cmd run dev
npm.cmd run test:web
npm.cmd run build:web
```

A interface fica em `http://127.0.0.1:4173/`. A suite `tests/test_web_mvp.mjs` cobre os
25 contratos obrigatorios e testes adicionais de bbox, configuracao e fail-closed. O
wrapper `tests/test_web_mvp.py` incorpora esses testes a suite completa. O build produz
`dist/frontend-build-manifest.json` com tamanho e SHA-256 de cada arquivo.

## Limitacoes

- a API nao fornece streaming de progresso;
- o overlay mostra componentes, mas nao inventa linhas de fluxo;
- impressao depende do dialogo e do mecanismo PDF do navegador;
- resultados automaticos, principalmente os marcados para revisao, exigem validacao humana;
- trocar a estrategia requer reiniciar o backend.
