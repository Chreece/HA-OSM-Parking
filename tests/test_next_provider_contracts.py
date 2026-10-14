"""Run next-provider contracts in a clean interpreter."""
from pathlib import Path
import subprocess
import sys
import unittest


class NextProviderSuite(unittest.TestCase):
    def test_fintraffic_and_tfl_contracts(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("next_provider_cases.py"))],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
