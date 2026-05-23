from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from qts.cli import main


ROOT = Path(__file__).resolve().parents[3]


class ConfigCliTests(unittest.TestCase):
    def test_config_validate_command_loads_runtime_config(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            exit_code = main(
                [
                    "config",
                    "validate",
                    "--config",
                    str(ROOT / "configs" / "backtest_fixture.yaml"),
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("valid BACKTEST config backtest-fixture-sma", stream.getvalue())

    def test_config_dump_outputs_effective_json(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            exit_code = main(
                [
                    "config",
                    "dump",
                    "--config",
                    str(ROOT / "configs" / "backtest_fixture.yaml"),
                ]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["strategies"][0]["parameters"], {"fast_window": 2, "slow_window": 3})
        self.assertEqual(payload["risk"]["sizing_parameters"], {"quantity": 10})


if __name__ == "__main__":
    unittest.main()
