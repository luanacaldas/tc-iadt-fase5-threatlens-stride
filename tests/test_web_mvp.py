from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WebMvpContractTests(unittest.TestCase):
    def test_frontend_contract_suite(self) -> None:
        result = subprocess.run(
            ["node", "--test", "tests/test_web_mvp.mjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
