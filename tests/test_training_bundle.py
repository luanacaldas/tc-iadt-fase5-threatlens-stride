from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.create_training_bundle import _dataset_files


class TrainingBundleTests(unittest.TestCase):
    def test_dataset_files_exclude_local_training_caches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "images" / "train" / "diagram.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"image")
            (image.parent / "diagram.npy").write_bytes(b"cache")
            (root / "labels.cache").write_bytes(b"cache")
            (root / "architecture.yaml").write_text("names: []\n", encoding="utf-8")
            (root / "architecture-replay.yaml").write_text("path: local\n", encoding="utf-8")

            bundled_names = {path.name for path in _dataset_files(root)}

            self.assertIn("diagram.jpg", bundled_names)
            self.assertIn("architecture.yaml", bundled_names)
            self.assertNotIn("diagram.npy", bundled_names)
            self.assertNotIn("labels.cache", bundled_names)
            self.assertNotIn("architecture-replay.yaml", bundled_names)


if __name__ == "__main__":
    unittest.main()
