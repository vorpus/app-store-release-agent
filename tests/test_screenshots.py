"""Offline validation tests for screenshot-upload inputs."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ASC_ISSUER_ID", "test-issuer")
os.environ.setdefault("ASC_KEY_ID", "test-key")
os.environ.setdefault("ASC_PRIVATE_KEY_PATH", "/tmp/not-read-in-these-tests.p8")
os.environ.setdefault("ASC_WORKSPACE_DIR", "/tmp/aso-agent-test-workspace")
sys.path.insert(0, "src")
import patch_metadata


def png_header(width: int = 100, height: int = 200) -> bytes:
    """Build the fixed header portion needed for the lightweight PNG validator."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big")


class ScreenshotValidationTests(unittest.TestCase):
    def test_resolves_inflight_first_release_without_live_version_file(self):
        original_get = patch_metadata.get
        try:
            patch_metadata.get = lambda path, params=None: {
                "data": [
                    {
                        "id": "inflight-id",
                        "attributes": {
                            "appStoreState": "PREPARE_FOR_SUBMISSION",
                            "versionString": "1.0",
                        },
                    }
                ]
            }
            self.assertEqual(
                patch_metadata._resolve_target_version("app-id", ""),
                ("1.0", "inflight-id", "PREPARE_FOR_SUBMISSION", ""),
            )
        finally:
            patch_metadata.get = original_get

    def test_accepts_regular_png_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "01-home.png"
            path.write_bytes(png_header())
            _, width, height = patch_metadata.validate_png(path)
            self.assertEqual((width, height), (100, 200))

    def test_rejects_wrong_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-an-image.png"
            path.write_bytes(b"not a png")
            with self.assertRaises(SystemExit):
                patch_metadata.validate_png(path)

    def test_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.png"
            link = Path(directory) / "link.png"
            target.write_bytes(png_header())
            link.symlink_to(target)
            with self.assertRaises(SystemExit):
                patch_metadata.validate_png(link)


if __name__ == "__main__":
    unittest.main()
