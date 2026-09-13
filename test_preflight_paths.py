"""Offline regression coverage for initial search-root validation only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import preflight_existing as preflight


class SearchRootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.missing = self.root / 'synthetic_missing_private'
        self.prompt = 'build examplewidget'

    def cli(self, name, payload, roots):
        return subprocess.run(
            [sys.executable, '-B', str(Path(__file__).with_name(name)),
             '--dirs', *[str(p) for p in roots]], input=payload,
            text=True, capture_output=True, timeout=10)

    def test_empty_valid_root(self):
        result = preflight.check(self.prompt, [str(self.root)])
        self.assertFalse(result['fired'])
        self.assertEqual(result['matches'], [])

    def test_missing_root(self):
        with self.assertRaises(ValueError):
            preflight.check(self.prompt, [str(self.missing)])

    def test_regular_file_root(self):
        path = self.root / 'examplewidget.txt'
        path.write_text('fixture', encoding='utf-8')
        with self.assertRaises(ValueError):
            preflight.check(self.prompt, [str(path)])

    def test_all_roots_validated_before_any_walk(self):
        for roots in [[self.root, self.missing], [self.missing, self.root]]:
            with self.subTest(roots_order=roots[0] == self.root):
                with patch.object(preflight.os, 'walk') as walk:
                    with self.assertRaises(ValueError):
                        preflight.check(self.prompt, [str(p) for p in roots])
                    walk.assert_not_called()

    def test_normal_hit(self):
        path = self.root / 'examplewidget.txt'
        path.write_text('fixture', encoding='utf-8')
        result = preflight.check(self.prompt, [str(self.root)])
        self.assertTrue(result['fired'])
        self.assertTrue(any(m['path'] == str(path) for m in result['matches']))

    def test_no_action_keeps_old_behavior(self):
        self.assertEqual(preflight.check('hello', [str(self.missing)]),
                         {'fired': False, 'terms': [], 'matches': []})

    def test_direct_search_rejects_empty_roots(self):
        with self.assertRaises(ValueError):
            preflight.search(['examplewidget'], [])

    def test_cli_missing_root_fixed_error(self):
        result = self.cli('preflight_existing.py', self.prompt, [self.missing])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), {'error': 'search_failed'})
        self.assertEqual(result.stderr, '')
        self.assertNotIn('synthetic_missing_private', result.stdout)

    def test_cli_valid_root_success(self):
        result = self.cli('preflight_existing.py', self.prompt, [self.root])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, '')
        self.assertFalse(json.loads(result.stdout)['fired'])

    def test_adapter_fixed_nonblocking_error(self):
        payload = json.dumps({'hook_event_name': 'UserPromptSubmit', 'prompt': self.prompt})
        result = self.cli('claude_adapter.py', payload, [self.root, self.missing])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, 'U1 hook: invalid input or inspection failed; no advice delivered.\n')


if __name__ == '__main__':
    unittest.main()
