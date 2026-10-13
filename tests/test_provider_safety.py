"""Run fault-injection tests separately from legacy Home Assistant stubs."""
from pathlib import Path
import subprocess
import sys
import unittest


class ProviderSafetySuite(unittest.TestCase):
    def test_isolated_safety_suite(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name('provider_safety_cases.py'))],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout + result.stderr)
