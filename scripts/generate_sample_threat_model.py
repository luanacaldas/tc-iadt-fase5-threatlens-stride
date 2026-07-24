"""Render the real delivery smoke result as a concise Markdown threat model."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/results/delivery-readiness/smoke-test-report.json"
OUTPUT = ROOT / "docs/sample-threat-model.md"


def _cell(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def build(payload: dict) -> str:
    phases = payload.get("phases") or []
    sample = next((phase.get("sampleAnalysis") for phase in phases if phase.get("sampleAnalysis")), None)
    if not isinstance(sample, dict):
        raise ValueError("Smoke report does not contain a real sample analysis")
    architecture = sample["architecture"]
    threats = sample["threats"]
    pipeline = sample["pipeline"]

    lines = [
        "# Relatório de exemplo de modelagem de ameaças",
        "",
        "> Resultado gerado por uma execução real do MVP 1.0.0-mvp. Os componentes e fluxos",
        "> são inferências automáticas e permanecem sujeitos à revisão humana.",
        "",
        "## Arquitetura analisada",
        "",
        "- Imagem: `data/sample-diagrams/02-mixed-components.jpg`.",
        f"- Detector: `{_cell(pipeline.get('detectorUsed'))}`.",
        f"- Estratégia de fluxos: `{_cell(pipeline.get('flowStrategy'))}`.",
        f"- Componentes detectados: {len(architecture.get('components') or [])}.",
        f"- Fluxos inferidos: {len(architecture.get('flows') or [])}.",
        f"- Ameaças geradas: {len(threats)}.",
        f"- Risco: {sample.get('score', {}).get('label')} ({sample.get('score', {}).get('value')}/10).",
        "",
        "## Componentes detectados",
        "",
        "| ID | Nome | Tipo | Provider | Confiança | Revisão |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for component in architecture.get("components") or []:
        lines.append(
            "| " + " | ".join(
                _cell(value)
                for value in (
                    component.get("id"), component.get("name"), component.get("type"),
                    component.get("provider"), component.get("confidence"), component.get("reviewStatus"),
                )
            ) + " |"
        )

    lines.extend([
        "",
        "## Fluxos inferidos",
        "",
        "| ID | Origem | Destino | Protocolo | Confiança | Evidência |",
        "| --- | --- | --- | --- | ---: | --- |",
    ])
    for flow in architecture.get("flows") or []:
        lines.append(
            "| " + " | ".join(
                _cell(value)
                for value in (
                    flow.get("id"), flow.get("from"), flow.get("to"), flow.get("protocol"),
                    flow.get("confidence"), flow.get("evidence"),
                )
            ) + " |"
        )

    lines.extend([
        "",
        "## Ameaças STRIDE, vulnerabilidades e contramedidas",
        "",
        "| STRIDE | Severidade | Ativo | Vulnerabilidade | Contramedidas |",
        "| --- | --- | --- | --- | --- |",
    ])
    for threat in threats:
        controls = "; ".join(str(value) for value in threat.get("countermeasures") or [])
        lines.append(
            "| " + " | ".join(
                _cell(value)
                for value in (
                    threat.get("stride"), threat.get("severity"), threat.get("componentName"),
                    threat.get("title"), controls,
                )
            ) + " |"
        )

    review_count = len(sample.get("humanReviewItems") or [])
    lines.extend([
        "",
        "## Limitações desta execução",
        "",
        f"- A execução gerou {review_count} itens para revisão humana.",
        "- A imagem é sintética e faz parte do conjunto gerado pelo projeto; não demonstra generalização.",
        "- Protocolos ausentes no diagrama permanecem `unknown` e não são inventados.",
        "- Fluxos inferidos por geometria podem conter conexões extras, ausentes ou invertidas.",
        "- A estratégia utilizada foi `legacy`; a estratégia controlada continua experimental e opt-in.",
        "- O relatório usa regras determinísticas e RAG local; chamadas remotas estavam desativadas.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    OUTPUT.write_text(build(payload), encoding="utf-8")
    print(f"Sample report written to {OUTPUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
