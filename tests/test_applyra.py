"""Offline behavior tests for the read-only Applyra provider."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
import json

sys.path.insert(0, "src")
import applyra


class ApplyraTests(unittest.TestCase):
    def test_validates_untrusted_cli_values(self):
        self.assertEqual(applyra.validate_slug("fictional-app"), "fictional-app")
        self.assertEqual(applyra.validate_country("us"), "US")
        with self.assertRaises(Exception):
            applyra.validate_slug("../../escape")
        with self.assertRaises(Exception):
            applyra.validate_country("USA")

    def test_cache_is_private_and_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "snapshot.json")
            applyra.atomic_json_write(Path(path), {"ok": True})
            self.assertEqual(json.loads(Path(path).read_text()), {"ok": True})
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_extracts_latest_position(self):
        snapshot = {
            "per_keyword": [
                {
                    "keyword": "fiction",
                    "ranks_history": {"data": {"apps": [{"history": [{"rank": 7}]}]}},
                }
            ]
        }
        self.assertEqual(applyra.latest_positions(snapshot), [{"keyword": "fiction", "position": 7}])


if __name__ == "__main__":
    unittest.main()
