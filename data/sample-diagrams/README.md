# Diagramas de demonstração

Estas quatro imagens foram geradas pelo próprio projeto com seeds determinísticas e
copiadas do benchmark estrutural `generated_known_graph`. Elas são autorizadas para a
demonstração, não dependem do download do dataset Kaggle e não são evidência de
generalização. O modelo não foi ajustado especificamente para esta pasta.

## 01-simple-api.jpg

- Objetivo: demonstrar uma cadeia curta entre usuário, Internet, API, computação e dados.
- Componentes esperados: `user`, `internet`, `api_gateway`, `compute`, `database` e `secrets_kms`.
- Fluxos relevantes: cinco relações sequenciais do usuário até o cofre de segredos.
- Ameaças esperadas: spoofing na entrada, adulteração em API/compute e divulgação de dados.
- Limitação conhecida: os protocolos visuais não são rotulados e podem permanecer `unknown`.
- Proveniência: seed `42271`, origem `current_arch_test_0001`.

## 02-mixed-components.jpg

- Objetivo: exercitar uma arquitetura com borda, entrega, API, persistência e observabilidade.
- Componentes esperados: `user`, `internet`, `cdn`, `api_gateway`, `compute`, `database`, `storage` e `monitoring`.
- Fluxos relevantes: sete relações sequenciais; a extração real pode produzir candidatos adicionais.
- Ameaças esperadas: spoofing, tampering, information disclosure e denial of service.
- Limitação conhecida: a geometria não equivale a um diagrama cloud real e pode gerar falsos fluxos.
- Proveniência: seed `42270`, origem `current_arch_test_0000`.

## 03-security-controls.jpg

- Objetivo: mostrar o efeito de um WAF antes da API sem tratar o controle como proteção absoluta.
- Componentes esperados: `user`, `internet`, `waf`, `api_gateway`, `compute` e `database`.
- Fluxos relevantes: cinco relações da entrada pública ao banco de dados.
- Ameaças esperadas: spoofing, tampering, information disclosure e denial of service.
- Limitação conhecida: o motor infere ameaças pela topologia e não valida a configuração real do WAF.
- Proveniência: seed `42272`, origem `current_arch_test_0002`.

## 04-dense-pipeline.jpg

- Objetivo: expor limites em um diagrama mais denso, com identidade, WAF e balanceamento.
- Componentes esperados: dez componentes, incluindo `identity_provider`, `waf`, `load_balancer` e `monitoring`.
- Fluxos relevantes: nove relações sequenciais com maior distância e mais oportunidades de ambiguidade.
- Ameaças esperadas: categorias STRIDE distribuídas entre entrada, identidade, processamento e dados.
- Limitação conhecida: densidade, linhas longas e proximidade geométrica podem gerar conexões extras ou ausentes.
- Proveniência: seed `42292`, origem `current_arch_test_0022`.
