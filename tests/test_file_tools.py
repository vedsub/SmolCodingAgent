import tempfile
import unittest
from pathlib import Path

from src.file_tools import resolve_workspace_file, read_file


class TestWorkspaceFileTools(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir()

        self.file = self.workspace / "basket.py"
        self.file.write_text(
            "def calculate_total(price, quantity):\n"
            "    return price + quantity\n",
            encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_file(self):
        result = resolve_workspace_file(self.workspace, "basket.py")
        self.assertEqual(result, self.file.resolve())

    def test_read_file(self):
        content = read_file(self.workspace, "basket.py")
        self.assertIn("calculate_total", content)

    def test_reject_absolute_path(self):
        with self.assertRaises(ValueError):
            resolve_workspace_file(self.workspace, str(self.file))

    def test_reject_parent_traversal(self):
        outside = Path(self.temp_dir.name) / "secret.txt"
        outside.write_text("secret")

        with self.assertRaises(ValueError):
            resolve_workspace_file(self.workspace, "../secret.txt")

    def test_reject_nonexistent_file(self):
        with self.assertRaises(FileNotFoundError):
            resolve_workspace_file(self.workspace, "missing.py")

    def test_reject_directory(self):
        folder = self.workspace / "folder"
        folder.mkdir()

        with self.assertRaises(ValueError):
            resolve_workspace_file(self.workspace, "folder")

    def test_reject_external_symlink(self):
        outside = Path(self.temp_dir.name) / "secret.txt"
        outside.write_text("secret")

        link = self.workspace / "secret_link.txt"
        link.symlink_to(outside)

        with self.assertRaises(ValueError):
            resolve_workspace_file(self.workspace, "secret_link.txt")


if __name__ == "__main__":
    unittest.main()