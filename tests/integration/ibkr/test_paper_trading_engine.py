from __future__ import annotations

import unittest
from pathlib import Path

from qts.core import load_runtime_config
from qts.engines import PaperTradingEngine


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "configs" / "paper_ibkr.yaml"


class IBKRPaperTradingEngineIntegrationTests(unittest.TestCase):
    def test_ibkr_paper_engine_initializes_without_credentials_in_mock_mode(self) -> None:
        config = load_runtime_config(
            CONFIG,
            env_path=None,
            overrides={"broker": {"safety": {"mock_mode": True}}},
        )

        status = PaperTradingEngine(config).start(max_events=0)

        self.assertTrue(status["initialized"])
        self.assertTrue(status["healthy"])
        self.assertTrue(status["mock_mode"])
        self.assertEqual(status["market_data_provider"], "external_events")
        self.assertEqual(status["reconciliation"]["status"], "matched")


if __name__ == "__main__":
    unittest.main()
