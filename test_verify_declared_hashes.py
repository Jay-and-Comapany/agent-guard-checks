#!/usr/bin/env python3
"""Offline regression tests for the adjacent fifth-check script.

Run: python3 -B -m unittest test_verify_declared_hashes -v
All HTTP subprocesses are mocked. Temporary fixture files are removed afterward.
"""
import hashlib
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


def load_check():
    source = Path(__file__).with_name("verify_declared_hashes.py").read_bytes()
    module = types.ModuleType("isolated_pack_hash_check")
    exec(compile(source, "<reviewed-hash-check>", "exec"), module.__dict__)
    return module


class HashCheckRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.check = load_check()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pack-hash-regression-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        no_network = patch.object(self.check.subprocess, "run", side_effect=AssertionError("network forbidden"))
        no_network.start()
        self.addCleanup(no_network.stop)

    def document(self, payload, name="artifact.bin"):
        doc = self.root / "receipt.md"
        doc.write_text(hashlib.sha256(payload).hexdigest() + "  " + name + "\n")
        return str(doc)

    def test_nonempty_match(self):
        (self.root / "artifact.bin").write_bytes(b"payload")
        result = self.check.verify([self.document(b"payload")])
        self.assertEqual(result, {"checked": 1, "defects": [], "unresolved": []})

    def test_empty_file_is_checked(self):
        (self.root / "artifact.bin").write_bytes(b"")
        result = self.check.verify([self.document(b"")])
        self.assertEqual(result, {"checked": 1, "defects": [], "unresolved": []})

    def test_bad_declared_hash_of_empty_file_is_detected(self):
        (self.root / "artifact.bin").write_bytes(b"")
        result = self.check.verify([self.document(b"not empty")])
        self.assertEqual(result["checked"], 1)
        self.assertEqual(len(result["defects"]), 1)
        self.assertEqual(result["unresolved"], [])

    def test_nested_path_does_not_validate_same_named_neighbor(self):
        (self.root / "nested").mkdir()
        (self.root / "nested/artifact.bin").write_bytes(b"actual nested file")
        (self.root / "artifact.bin").write_bytes(b"different neighbor")
        result = self.check.verify([self.document(b"different neighbor", "nested/artifact.bin")])
        # A correct result either checks the declared nested file and finds the
        # mismatch, or rejects that unsupported path. Silently checking the
        # neighbor and reporting a matching hash is never acceptable.
        self.assertTrue(result["defects"] or result["unresolved"], result)

    def test_empty_local_file_does_not_trigger_url_fallback(self):
        (self.root / "artifact.bin").write_bytes(b"")
        with patch.object(self.check, "_read_url", return_value=b"remote") as remote:
            result = self.check.verify([self.document(b"")], fetch_urls=True)
        remote.assert_not_called()
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["defects"], [])

    def test_existing_url_flag_is_local_first_not_remote_proof(self):
        (self.root / "artifact.bin").write_bytes(b"local")
        doc = self.document(b"local")
        with open(doc, "a") as stream:
            stream.write("https://example.invalid/artifact.bin\n")
        with patch.object(self.check, "_read_url", return_value=b"different remote") as remote:
            result = self.check.verify([doc], fetch_urls=True)
        remote.assert_not_called()
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["defects"], [])

    def test_parent_and_absolute_paths_are_not_neighbor_aliases(self):
        (self.root / "artifact.bin").write_bytes(b"neighbor")
        for name in ("../artifact.bin", str(self.root / "artifact.bin")):
            with self.subTest(name=name):
                result = self.check.verify([self.document(b"neighbor", name)])
                self.assertEqual(result["checked"], 0)
                self.assertEqual(len(result["unresolved"]), 1)

    def test_remote_empty_success_is_distinct_from_failure(self):
        url = "https://example.invalid/artifact.bin"
        with patch.object(self.check.subprocess, "run", return_value=types.SimpleNamespace(stdout=b"", returncode=0)):
            self.assertEqual(self.check._read_url([url], "artifact.bin"), b"")
        with patch.object(self.check.subprocess, "run", return_value=types.SimpleNamespace(stdout=b"partial body", returncode=22)):
            self.assertIsNone(self.check._read_url([url], "artifact.bin"))

    def test_mismatch_labels_remain_conventions(self):
        (self.root / "artifact.bin").write_bytes(b"real")
        actual = hashlib.sha256(b"real").hexdigest()
        changed = actual[:16] + ("0" if actual[16] != "0" else "1") + actual[17:]
        doc = self.root / "receipt.md"
        doc.write_text(changed + "  artifact.bin\n")
        result = self.check.verify([str(doc)])
        self.assertEqual(result["defects"][0]["prefix_match"], 16)
        self.assertEqual(result["defects"][0]["verdict"], "fabricated")

    def test_url_suffix_is_not_filename_identity(self):
        with patch.object(self.check.subprocess, "run") as fetch:
            self.assertIsNone(self.check._read_url(
                ["https://example.invalid/not-artifact.bin"], "artifact.bin"))
        fetch.assert_not_called()

    def test_url_exact_filename_query_fragment_and_encoding(self):
        url = "https://example.invalid/files/%61rtifact.bin?download=1#checksum"
        response = types.SimpleNamespace(stdout=b"right file", returncode=0)
        with patch.object(self.check.subprocess, "run", return_value=response) as fetch:
            self.assertEqual(self.check._read_url([
                "https://example.invalid/not-artifact.bin", url], "artifact.bin"), b"right file")
        args = fetch.call_args.args[0]
        self.assertEqual(args[-1], url.split("#")[0])
        self.assertEqual(args[args.index("--proto") + 1], "=https")
        self.assertEqual(args[args.index("--proto-redir") + 1], "=https")

    def test_url_multiple_distinct_candidates_are_unresolved(self):
        pairs = (
            ["https://one.invalid/artifact.bin", "https://two.invalid/artifact.bin"],
            ["https://example.invalid/artifact.bin?v=1", "https://example.invalid/artifact.bin?v=2"],
        )
        for urls in pairs:
            with self.subTest(urls=urls), patch.object(self.check.subprocess, "run") as fetch:
                self.assertIsNone(self.check._read_url(urls, "artifact.bin"))
                fetch.assert_not_called()

    def test_url_duplicate_fragments_do_not_create_ambiguity(self):
        url = "https://example.invalid/artifact.bin"
        response = types.SimpleNamespace(stdout=b"same file", returncode=0)
        with patch.object(self.check.subprocess, "run", return_value=response) as fetch:
            self.assertEqual(self.check._read_url([url, url + "#a", url + "#b"], "artifact.bin"), b"same file")
        fetch.assert_called_once()

    def test_url_malformed_non_https_or_non_file_path_is_not_fetched(self):
        urls = [
            "http://example.invalid/artifact.bin", "file:///artifact.bin",
            "https:///artifact.bin", "https://[bad/artifact.bin",
            "https://example.invalid:bad/artifact.bin", "https://user@example.invalid/artifact.bin",
            "https://example.invalid/artifact.bin/", "https://example.invalid/?file=artifact.bin",
            "https://example.invalid/nested%2Fartifact.bin", "https://example.invalid/artifact.bin?bad=%ZZ",
            "https://example.invalid/%FFartifact.bin", "https://example.invalid/\nartifact.bin",
        ]
        for url in urls:
            with self.subTest(url=url), patch.object(self.check.subprocess, "run") as fetch:
                self.assertIsNone(self.check._read_url([url], "artifact.bin"))
                fetch.assert_not_called()

    def test_unavailable_curl_is_unresolved(self):
        with patch.object(self.check.subprocess, "run", side_effect=FileNotFoundError("curl")):
            self.assertIsNone(self.check._read_url(["https://example.invalid/artifact.bin"], "artifact.bin"))

    def test_document_url_fallback_integration_is_explicit(self):
        doc = self.document(b"download")
        with open(doc, "a") as stream:
            stream.write("[download](https://example.invalid/artifact.bin?v=5#here)\n")
        self.assertEqual(self.check.verify([doc]), {"checked": 0, "defects": [], "unresolved": [{"doc": doc, "file": "artifact.bin"}]})
        response = types.SimpleNamespace(stdout=b"download", returncode=0)
        with patch.object(self.check.subprocess, "run", return_value=response) as fetch:
            self.assertEqual(self.check.verify([doc], fetch_urls=True), {"checked": 1, "defects": [], "unresolved": []})
        fetch.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
