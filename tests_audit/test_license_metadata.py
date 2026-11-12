"""Current distribution metadata must match the root MIT license."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LicenseMetadata(unittest.TestCase):
    def test_current_distribution_metadata(self):
        license_text = (ROOT / "LICENSE").read_text()
        self.assertTrue(license_text.startswith("MIT License"))
        self.assertIn("Zero State LLC", license_text)
        files = [ROOT / "SKILL.md", ROOT / "README.md"]
        files += list((ROOT / "skills").glob("*/SKILL.md"))
        files += list((ROOT / "skills").glob("*/README.md"))
        files += [
            p
            for p in [
                ROOT / "manifest.json",
                ROOT / "references/manifest.json",
                ROOT / "hyperlex.manifest.yaml",
                ROOT / "pyproject.toml",
            ]
            if p.exists()
        ]
        for p in files:
            with self.subTest(path=str(p)):
                self.assertNotRegex(
                    p.read_text(), r"Proprietary|ZSPL|LicenseRef-Zero-State"
                )
        self.assertIn("license: MIT", (ROOT / "SKILL.md").read_text())


if __name__ == "__main__":
    unittest.main()
