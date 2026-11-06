
import tempfile
import unittest
from pathlib import Path

from src.file_tools import run_tests


class TestRunTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

        (self.workspace / "tests").mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_successful_tests(self):
        test_file = self.workspace / "tests" / "test_example.py"

        test_file.write_text(
            "import unittest\n"
            "class ExampleTest(unittest.TestCase):\n"
            "    def test_addition(self):\n"
            "        self.assertEqual(1 + 1, 2)\n",
            encoding="utf-8",
        )

        result = run_tests(self.workspace)

        self.assertTrue(result["success"])
        self.assertEqual(result["tests_run"], 1)

    def test_zero_tests_rejected(self):
        test_file = self.workspace / "tests" / "test_empty.py"

        test_file.write_text(
            "x = 10\n",
            encoding="utf-8",
        )

        with self.assertRaises(RuntimeError):
            run_tests(self.workspace)

    def test_failed_assertion_rejected(self):
        test_file = self.workspace / "tests" / "test_failure.py"

        test_file.write_text(
            "import unittest\n"
            "class FailureTest(unittest.TestCase):\n"
            "    def test_failure(self):\n"
            "        self.assertEqual(1, 2)\n",
            encoding="utf-8",
        )

        with self.assertRaises(RuntimeError):
            run_tests(self.workspace)

    def test_skipped_test_rejected(self):
        test_file = self.workspace / "tests" / "test_skipped.py"

        test_file.write_text(
            "import unittest\n"
            "class SkippedTest(unittest.TestCase):\n"
            "    @unittest.skip('deliberate skip')\n"
            "    def test_skip(self):\n"
            "        pass\n",
            encoding="utf-8",
        )

        with self.assertRaises(RuntimeError):
            run_tests(self.workspace)

    def test_timeout(self):
        test_file = self.workspace / "tests" / "test_hang.py"

        test_file.write_text(
            "import unittest\n"
            "class HangTest(unittest.TestCase):\n"
            "    def test_hang(self):\n"
            "        while True:\n"
            "            pass\n",
            encoding="utf-8",
        )

        with self.assertRaises(TimeoutError):
            run_tests(self.workspace, timeout=1)


if __name__ == "__main__":
    unittest.main()
