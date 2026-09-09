"""Offline contract fixtures; not a live Claude integration test."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from claude_adapter import adapt


class AdapterTests(unittest.TestCase):
    def test_prompt(self):
        result = adapt({'hook_event_name': 'UserPromptSubmit', 'prompt': '違う'})
        self.assertEqual(result['hookSpecificOutput']['hookEventName'], 'UserPromptSubmit')

    def test_metadata_not_prompt(self):
        self.assertEqual(adapt({'hook_event_name': 'UserPromptSubmit',
                                'prompt': 'ありがとう', 'cwd': '/違う'}), {})

    def test_no_implicit_search(self):
        with patch('claude_adapter.preflight') as search:
            adapt({'hook_event_name': 'UserPromptSubmit', 'prompt': 'build widget'})
            search.assert_not_called()

    def test_explicit_search(self):
        with patch('claude_adapter.preflight', return_value={'fired': True}) as search:
            result = adapt({'hook_event_name': 'UserPromptSubmit', 'prompt': 'build widget'}, ['fixtures'])
            search.assert_called_once_with('build widget', ['fixtures'])
            self.assertIn('additionalContext', result['hookSpecificOutput'])

    def test_command_is_data(self):
        result = adapt({'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
                        'tool_input': {'command': 'rm -rf fixture-do-not-execute'}})
        self.assertEqual(set(result['hookSpecificOutput']), {'hookEventName', 'additionalContext'})

    def test_other_tool(self):
        self.assertEqual(adapt({'hook_event_name': 'PreToolUse', 'tool_name': 'Read'}), {})

    def test_read_only(self):
        self.assertEqual(adapt({'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
                                'tool_input': {'command': 'ls'}}), {})

    def test_stop_metadata_not_evidence(self):
        for message in ['完了しました', '修正しました。まだ次の作業はしていません。',
                        '修正しました。テストは不一致でした。', 'Fixed. Not done with the next task.']:
            with self.subTest(message=message):
                result = adapt({'hook_event_name': 'Stop', 'stop_hook_active': False,
                                'last_assistant_message': message, 'cwd': '/PASS'})
                self.assertEqual(result['hookSpecificOutput']['hookEventName'], 'Stop')

    def test_stop_loop(self):
        self.assertEqual(adapt({'hook_event_name': 'Stop', 'stop_hook_active': True,
                                'last_assistant_message': '完了しました'}), {})

    def test_stop_evidence(self):
        self.assertEqual(adapt({'hook_event_name': 'Stop', 'stop_hook_active': False,
                                'last_assistant_message': '完了しました。3/3 PASS'}), {})

    def test_invalid(self):
        for event in [[], {}, {'hook_event_name': 'Unknown'},
                      {'hook_event_name': 'UserPromptSubmit', 'prompt': {}},
                      {'hook_event_name': 'Stop', 'stop_hook_active': 'false'},
                      {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash'}]:
            with self.subTest(event=event), self.assertRaises(ValueError):
                adapt(event)

    def test_cli(self):
        path = Path(__file__).with_name('claude_adapter.py')
        for payload, status in [('not-json-sensitive-marker', 1),
                                (json.dumps({'hook_event_name': 'UserPromptSubmit', 'prompt': 'ありがとう'}), 0)]:
            result = subprocess.run([sys.executable, '-B', str(path)], input=payload,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, status)
            self.assertNotIn('sensitive-marker', result.stderr)
            if status == 0:
                self.assertEqual(json.loads(result.stdout), {})
            else:
                self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
