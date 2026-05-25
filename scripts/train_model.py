#!/usr/bin/env python3
"""Train the Phase 7 dependency-free directional ML baseline."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from qts.core import ConfigurationError, DataError
from qts.ml import MLWorkflowError
from qts.workflows import train_model_workflow


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="configs/ml/directional_baseline.yaml",
        help="ML training config path",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="override model registry output directory",
    )
    args = parser.parse_args(argv)

    try:
        result = train_model_workflow(args.config, output_dir=args.output_dir)
    except (ConfigurationError, DataError, MLWorkflowError, ValueError) as exc:
        print(f"model training failed: {exc}")
        return 2

    model = result["model"]
    metrics = result["metrics"]
    artifact_path = result["artifact_path"]
    manifest_path = result["manifest_path"]
    validation = metrics["validation"]
    print(
        f"trained model {model.model_id}: "
        f"samples={metrics['train']['sample_count'] + validation['sample_count'] + metrics['test']['sample_count']} "
        f"validation_accuracy={validation['accuracy']} "
        f"artifact={artifact_path} "
        f"manifest={manifest_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
