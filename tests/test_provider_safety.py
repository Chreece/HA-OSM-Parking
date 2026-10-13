"""Run fault-injection tests separately from legacy Home Assistant stubs."""
from pathlib import Path
import subprocess
import sys
import unittest


class ProviderSafetySuite(unittest.TestCase):
    def test_isolated_safety_suite(self):
        for filename in ('provider_safety_cases.py', 'provider_followup_cases.py'):
            with self.subTest(suite=filename):
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).with_name(filename))],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                print(result.stdout + result.stderr)
