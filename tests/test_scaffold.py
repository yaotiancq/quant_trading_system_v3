from __future__ import annotations

import importlib
import sys
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class ScaffoldSmokeTests(unittest.TestCase):
    def test_required_docs_exist(self) -> None:
        for name in (
            "SYSTEM_DESIGN.md",
            "PHASE_PLAN.md",
            "INTERFACES.md",
            "DATA_MODELS.md",
            "DECISIONS.md",
            "PROJECT_STATE.md",
            "CHANGELOG.md",
        ):
            self.assertTrue((ROOT / name).is_file(), name)

    def test_package_modules_import(self) -> None:
        for module_name in (
            "qts",
            "qts.core",
            "qts.domain",
            "qts.market_data",
            "qts.features",
            "qts.strategies",
            "qts.ml",
            "qts.risk",
            "qts.execution",
            "qts.brokers",
            "qts.brokers.backtest",
            "qts.brokers.alpaca",
            "qts.integrations",
            "qts.integrations.alpaca",
            "qts.integrations.futu",
            "qts.integrations.polygon",
            "qts.portfolio",
            "qts.engines",
            "qts.reporting",
            "qts.monitoring",
            "qts.research",
            "qts.utils",
        ):
            with self.subTest(module=module_name):
                importlib.import_module(module_name)

    def test_config_templates_exist(self) -> None:
        for name in ("base.yaml", "backtest.yaml", "paper_alpaca.yaml", "live_alpaca.yaml"):
            self.assertTrue((ROOT / "configs" / name).is_file(), name)

    def test_pyproject_declares_src_package(self) -> None:
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(data["project"]["name"], "quant-trading-system-v3")
        self.assertEqual(data["tool"]["setuptools"]["package-dir"][""], "src")
        self.assertEqual(data["project"]["scripts"]["qts"], "qts.cli:main")

    def test_package_version_is_available(self) -> None:
        qts = importlib.import_module("qts")

        self.assertEqual(qts.__version__, "0.0.0")


if __name__ == "__main__":
    unittest.main()
