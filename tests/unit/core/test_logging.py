from __future__ import annotations

import logging
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

from qts.core import configure_logging


class LoggingTests(unittest.TestCase):
    def test_configure_logging_returns_project_logger_and_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "qts.log"
            with redirect_stderr(StringIO()):
                logger = configure_logging(level="INFO", structured=True, log_file=log_path)
                logger.info("hello")

            logging.shutdown()

            self.assertEqual(logger.name, "qts")
            self.assertIn('"message": "hello"', log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
