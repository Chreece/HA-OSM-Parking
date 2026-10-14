"""Run the action tests in a clean interpreter isolated from legacy HA stubs."""
from pathlib import Path
import subprocess
import sys
import unittest


class ActionServiceSuite(unittest.TestCase):
    def test_action_service_cases(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("action_service_cases.py"))],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
