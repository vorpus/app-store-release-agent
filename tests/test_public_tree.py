"""Tests for the public-repository path policy."""
import sys
from pathlib import PurePosixPath

sys.path.insert(0, "scripts")
from verify_public_tree import is_forbidden

import unittest


class PublicTreePolicyTests(unittest.TestCase):
    def test_rejects_runtime_metadata(self):
        self.assertIsNotNone(is_forbidden(PurePosixPath("metadata/app/app-id.txt")))

    def test_rejects_provider_runtime_data(self):
        self.assertIsNotNone(is_forbidden(PurePosixPath("cache/applyra.json")))

    def test_allows_synthetic_example(self):
        self.assertIsNone(
            is_forbidden(PurePosixPath("examples/synthetic-app/fictional-app/app-id.txt"))
        )


if __name__ == "__main__":
    unittest.main()
