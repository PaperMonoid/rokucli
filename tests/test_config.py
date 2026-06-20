from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from rokucli.config import load_host, save_host


class ConfigTests(unittest.TestCase):
    def test_missing_config_returns_none(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(load_host(Path(directory) / "missing.json"))

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "config.json"
            save_host("192.0.2.10", path)
            self.assertEqual(load_host(path), "192.0.2.10")


if __name__ == "__main__":
    unittest.main()

