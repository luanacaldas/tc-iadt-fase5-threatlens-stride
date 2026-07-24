"""Evaluate deterministic STRIDE architecture rules against hand-authored scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.stride_engine import FLOW_RULES, analyze_architecture


def _safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def score_rule_sets(expected: set[str], predicted: set[str]) -> dict:
    true_positive = expected & predicted
    false_positive = predicted - expected
    false_negative = expected - predicted
    precision = _safe_divide(len(true_positive), len(predicted))
    recall = _safe_divide(len(true_positive), len(expected))
    if not expected and not predicted:
        precision = recall = 1.0
    return {
        "truePositive": sorted(true_positive),
        "falsePositive": sorted(false_positive),
        "falseNegative": sorted(false_negative),
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "exactMatch": not false_positive and not false_negative,
    }


def evaluate_scenarios(golden_set: dict) -> dict:
    known_rules = {rule["id"] for rule in FLOW_RULES}
    covered_rules: set[str] = set()
    per_scenario = []
    total_tp = total_fp = total_fn = 0

    for scenario in golden_set["scenarios"]:
        expected = set(scenario["expectedRuleIds"])
        unknown_expected = expected - known_rules
        if unknown_expected:
            raise ValueError(
                f"Scenario {scenario['id']} references unknown rules: {sorted(unknown_expected)}"
            )
        covered_rules.update(expected)
        analysis = analyze_architecture(scenario["architecture"])
        predicted = {
            threat["ruleId"]
            for threat in analysis["threats"]
            if threat.get("source") == "flow-rule" and threat.get("ruleId")
        }
        metrics = score_rule_sets(expected, predicted)
        total_tp += len(metrics["truePositive"])
        total_fp += len(metrics["falsePositive"])
        total_fn += len(metrics["falseNegative"])
        per_scenario.append(
            {
                "id": scenario["id"],
                "description": scenario["description"],
                "expectedRuleIds": sorted(expected),
                "predictedRuleIds": sorted(predicted),
                "metrics": metrics,
            }
        )

    precision = _safe_divide(total_tp, total_tp + total_fp)
    recall = _safe_divide(total_tp, total_tp + total_fn)
    exact_matches = sum(item["metrics"]["exactMatch"] for item in per_scenario)
    aggregate = {
        "scenarioCount": len(per_scenario),
        "truePositive": total_tp,
        "falsePositive": total_fp,
        "falseNegative": total_fn,
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "exactMatchCount": exact_matches,
        "exactMatchRate": _safe_divide(exact_matches, len(per_scenario)),
        "knownRuleCount": len(known_rules),
        "coveredRuleCount": len(covered_rules),
        "ruleCoverage": _safe_divide(len(covered_rules), len(known_rules)),
        "uncoveredRuleIds": sorted(known_rules - covered_rules),
    }
    return {
        "schemaVersion": "1.0",
        "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "passed"
        if aggregate["exactMatchRate"] == 1.0 and aggregate["ruleCoverage"] == 1.0
        else "failed",
        "aggregate": aggregate,
        "perScenario": per_scenario,
    }


def evaluate(golden_path: Path, output_dir: Path) -> dict:
    golden_set = json.loads(golden_path.read_text(encoding="utf-8"))
    result = evaluate_scenarios(golden_set)
    result["goldenSet"] = str(golden_path.resolve())
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "stride-golden-evaluation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    _write_markdown(result, output_dir / "stride-golden-evaluation.md")
    return result


def _write_markdown(result: dict, output: Path) -> None:
    aggregate = result["aggregate"]
    lines = [
        "# STRIDE Golden Set Evaluation",
        "",
        f"- Status: **{result['status']}**",
        f"- Scenarios: {aggregate['scenarioCount']}",
        f"- Rule coverage: {aggregate['coveredRuleCount']}/{aggregate['knownRuleCount']} ({aggregate['ruleCoverage']:.2%})",
        f"- Precision: {aggregate['precision']:.4f}",
        f"- Recall: {aggregate['recall']:.4f}",
        f"- F1: {aggregate['f1']:.4f}",
        f"- Exact scenario matches: {aggregate['exactMatchCount']}/{aggregate['scenarioCount']} ({aggregate['exactMatchRate']:.2%})",
        "",
        "## Scenarios",
        "",
    ]
    for scenario in result["perScenario"]:
        marker = "PASS" if scenario["metrics"]["exactMatch"] else "FAIL"
        lines.append(f"- **{marker} - {scenario['id']}**: {scenario['description']}")
    lines += [
        "",
        "This is a deterministic regression and acceptance benchmark. It does not measure visual model generalization or generative report quality.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--golden-set",
        type=Path,
        default=Path("data/benchmarks/stride/golden-set.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/results/stride-golden"),
    )
    args = parser.parse_args()
    result = evaluate(args.golden_set, args.output)
    aggregate = result["aggregate"]
    print(
        "STRIDE golden set: "
        f"status={result['status']}, F1={aggregate['f1']:.4f}, "
        f"exact={aggregate['exactMatchRate']:.2%}, coverage={aggregate['ruleCoverage']:.2%}"
    )
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
