"""Run the end-to-end dataset preparation and YOLO training pipeline.

This command chains the three critical steps in order:
1. Consolidate and normalize datasets.
2. Analyze balance and integrity.
3. Train YOLO on the prepared dataset.

The script is intentionally thin and delegates real work to the existing
project scripts so each stage can still be run independently.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _python() -> str:
    return sys.executable


def _run(command: list[str]) -> None:
    print(f"[pipeline] Running: {' '.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare dataset, analyze balance and train YOLO in one command")
    parser.add_argument("--source", action="append", default=[], help="Dataset source directory. Repeat for multiple sources.")
    parser.add_argument("--class-file", action="append", default=[], help="Optional class-file per source, in the same order as --source.")
    parser.add_argument("--output", default="dataset", help="Output dataset directory (default: dataset)")
    parser.add_argument("--device", default="0", help="YOLO device: 0 or cpu")
    parser.add_argument("--epochs", type=int, default=100, help="YOLO epochs")
    parser.add_argument("--model", default="yolov8n.pt", help="Base YOLO model")
    parser.add_argument("--skip-prepare", action="store_true", help="Skip dataset preparation")
    parser.add_argument("--skip-analyze", action="store_true", help="Skip dataset balance analysis")
    parser.add_argument("--skip-train", action="store_true", help="Skip YOLO training")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run dataset preparation")
    args = parser.parse_args()

    if not args.skip_prepare:
        prepare_command = [_python(), "scripts/prepare_dataset.py"]
        for source in args.source:
            prepare_command.extend(["--source", source])
        for class_file in args.class_file:
            prepare_command.extend(["--class-file", class_file])
        prepare_command.extend(["--output", args.output])
        if args.dry_run:
            prepare_command.append("--dry-run")
        _run(prepare_command)

    if not args.skip_analyze:
        analyze_command = [_python(), "scripts/analyze_dataset_balance.py", "--data", str(Path(args.output) / "architecture.yaml")]
        _run(analyze_command)

    if not args.skip_train:
        train_command = [_python(), "scripts/train_yolo.py", "--device", args.device, "--epochs", str(args.epochs), "--model", args.model]
        _run(train_command)


if __name__ == "__main__":
    main()