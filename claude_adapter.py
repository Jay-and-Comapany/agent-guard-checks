#!/usr/bin/env python3
"""Claude event JSON -> advisory context. No commands executed or logs written.

Invalid input exits 1 (nonblocking hook error), NOT a security boundary.
Stop feedback can cause one extra model turn; stop_hook_active prevents recursion.
Filesystem preflight is disabled unless --dirs is explicitly supplied.
"""
import argparse
import json
import sys

from capture_correction import check as correction
from check_completion_claims import check as completion
from guard_irreversible import check as irreversible
from preflight_existing import check as preflight


def string_field(obj, key):
    value = obj.get(key)
    if not isinstance(value, str):
        raise ValueError('missing or invalid field')
    return value


def adapt(event, dirs=()):
    if not isinstance(event, dict):
        raise ValueError('expected object')
    name = string_field(event, 'hook_event_name')
    advice = []
    if name == 'UserPromptSubmit':
        prompt = string_field(event, 'prompt')
        result = correction(prompt)
        if result['fired']:
            advice.append(result['prompt'])
        if dirs:
            result = preflight(prompt, dirs)
            if result['fired']:
                advice.append('指定範囲に既存材料の候補があります。新規作成前に確認してください。'
                              '検索は限定的であり、一致は内容の正しさを保証しません。')
    elif name == 'PreToolUse':
        if string_field(event, 'tool_name') != 'Bash':
            return {}
        tool_input = event.get('tool_input')
        if not isinstance(tool_input, dict):
            raise ValueError('invalid tool input')
        result = irreversible(string_field(tool_input, 'command'))
        if result['fired']:
            advice.extend(result['checklist'])
    elif name == 'Stop':
        active = event.get('stop_hook_active')
        if type(active) is not bool:
            raise ValueError('invalid stop state')
        if active:
            return {}
        result = completion(string_field(event, 'last_assistant_message'))
        if result['fired']:
            advice.append(result['advice'])
    else:
        raise ValueError('unsupported event')
    if not advice:
        return {}
    return {'hookSpecificOutput': {
        'hookEventName': name, 'additionalContext': '\n'.join(advice)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dirs', nargs='+', default=[])
    args = parser.parse_args()
    try:
        result = adapt(json.load(sys.stdin), args.dirs)
    except (ValueError, TypeError, OSError):
        print('U1 hook: invalid input or inspection failed; no advice delivered.', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
