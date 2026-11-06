import tempfile
import unittest
import stat

from pathlib import Path

from src.file_tools import apply_patch


class TestFilePatching(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir()

        self.file = self.workspace / "basket.py"

        self.original_content = (
            "def calculate_total(price, quantity):\n"
            "    return price + quantity\n"
        )

        self.file.write_text(
            self.original_content,
            encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_successful_patch(self):
        apply_patch(
            self.workspace,
            "basket.py",
            "price + quantity",
            "price * quantity"
        )

        content = self.file.read_text(encoding="utf-8")

        self.assertIn("price * quantity", content)
        self.assertNotIn("price + quantity", content)

    def test_reject_missing_old_text(self):
        before = self.file.read_text(encoding="utf-8")

        with self.assertRaises(ValueError):
            apply_patch(
                self.workspace,
                "basket.py",
                "price - quantity",
                "price * quantity"
            )

        after = self.file.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_reject_ambiguous_old_text(self):
        self.file.write_text(
            "price + quantity\nprice + quantity\n",
            encoding="utf-8"
        )

        before = self.file.read_text(encoding="utf-8")

        with self.assertRaises(ValueError):
            apply_patch(
                self.workspace,
                "basket.py",
                "price + quantity",
                "price * quantity"
            )

        after = self.file.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_preserve_file_permissions(self):
        self.file.chmod(0o755)

        apply_patch(
            self.workspace,
            "basket.py",
            "price + quantity",
            "price * quantity"
        )

        mode = stat.S_IMODE(self.file.stat().st_mode)

        self.assertEqual(mode, 0o755)

    def test_no_temporary_file_after_patch(self):
        apply_patch(
            self.workspace,
            "basket.py",
            "price + quantity",
            "price * quantity"
        )

        leftovers = list(self.workspace.glob(".patch_*.tmp"))

        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()