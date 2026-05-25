from __future__ import annotations

import importlib.util
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
RUN_BACKTEST_SCRIPT = ROOT / "scripts" / "run_backtest.py"
spec = importlib.util.spec_from_file_location("run_backtest_wrapper_under_test", RUN_BACKTEST_SCRIPT)
assert spec is not None
run_backtest = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(run_backtest)


class CLIWrapperTests(unittest.TestCase):
    def test_backtest_script_delegates_to_workflow(self) -> None:
        result = SimpleNamespace(
            run_id="delegated-backtest",
            fills=[object(), object()],
            metrics={"total_return": 0.123456},
            artifacts={"summary": "summary.md"},
        )

        with (
            patch.object(run_backtest, "run_backtest_workflow", return_value=result) as workflow,
            patch("sys.stdout", new_callable=StringIO) as stdout,
        ):
            exit_code = run_backtest.main(["--config", "custom.yaml", "--output-dir", "out"])

        self.assertEqual(exit_code, 0)
        workflow.assert_called_once_with("custom.yaml", output_dir="out", env_path=".env")
        self.assertIn("delegated-backtest", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
