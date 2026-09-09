#!/usr/bin/env python3
"""run_tests.py — 検査4本の反証テスト(negative test)。各検査について
「発火すべきで発火する」「発火すべきでなく発火しない」の両方を確かめる。
実行: python3 run_tests.py  → PASS/FAIL を1行ずつ、最後に合計。終了コードはFAILがあれば1。
"""
import subprocess, sys, os, json, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
def run(script, stdin='', args=()):
    p = subprocess.run([sys.executable, os.path.join(HERE, script), *args], input=stdin, capture_output=True, text=True)
    return json.loads(p.stdout.strip().splitlines()[-1]), p.returncode

results = []
def expect(name, cond):
    results.append((name, bool(cond))); print(('PASS ' if cond else 'FAIL ') + name)

# 1. check_completion_claims
r, _ = run('check_completion_claims.py', '修正を完了しました。')
expect('claims: fires on completion claim without evidence', r['fired'])
r, _ = run('check_completion_claims.py', '修正を完了しました。テストは 3/3 PASS、read-backで一致。')
expect('claims: does not fire when evidence present', not r['fired'])
r, _ = run('check_completion_claims.py', 'まだ修正できていません。')
expect('claims: does not fire on negated claim', not r['fired'])
r, _ = run('check_completion_claims.py', '次は設計を見直します。')
expect('claims: does not fire without a claim', not r['fired'])
_, code = run('check_completion_claims.py', 'published.', ('--strict',))
expect('claims: --strict returns exit 2 when fired', code == 2)

# 2. guard_irreversible
r, _ = run('guard_irreversible.py', args=('rm -rf build/',))
expect('guard: fires on rm -rf', r['fired'] and 'DESTRUCTIVE' in r['kinds'])
r, _ = run('guard_irreversible.py', "cat > note.md <<'EOF'\nrm -rf everything\nEOF")
expect('guard: does not fire on rm inside heredoc data', not r['fired'])
r, _ = run('guard_irreversible.py', args=('echo "rm -rf /"',))
expect('guard: does not fire on rm inside quoted string', not r['fired'])
r, _ = run('guard_irreversible.py', args=('ls -la',))
expect('guard: does not fire on read-only command', not r['fired'])
r, _ = run('guard_irreversible.py', args=('curl -s -X POST https://api.example.com/items -d @x.json',))
expect('guard: fires on external POST', r['fired'] and 'EXTERNAL' in r['kinds'])
r, _ = run('guard_irreversible.py', args=('./lock.sh acquire me | head -1 && python3 write.py',))
expect('guard: fires on masked lock acquire', r['fired'] and 'LOCK_MASKED' in r['kinds'])

# 3. capture_correction
r, _ = run('capture_correction.py', '違う、そういう意味じゃない')
expect('correction: fires on negation', r['fired'] and '否定' in r['kinds'])
r, _ = run('capture_correction.py', 'ありがとう、助かった')
expect('correction: does not fire on thanks', not r['fired'])
r, _ = run('capture_correction.py', "No, that's not what I asked")
expect('correction: fires on English negation', r['fired'])
with tempfile.TemporaryDirectory() as d:
    log = os.path.join(d, 'c.jsonl')
    run('capture_correction.py', '端的に言って', ('--log', log))
    expect('correction: --log appends a JSONL record', os.path.exists(log) and len(open(log).read().splitlines()) == 1)

# 4. preflight_existing
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'estat_extract.py'), 'w').write('# e-Stat extractor\n')
    r, _ = run('preflight_existing.py', 'estatの抽出スクリプトを新しく作って', ('--dirs', d))
    expect('preflight: finds existing file by identifier', r['fired'] and any('estat' in m['path'] for m in r['matches']))
    r, _ = run('preflight_existing.py', 'weatherの集計ツールを作って', ('--dirs', d))
    expect('preflight: does not fire when nothing matches', not r['fired'])
    r, _ = run('preflight_existing.py', 'estatについて雑談しよう', ('--dirs', d))
    expect('preflight: does not fire without an action verb', not r['fired'])

n_fail = sum(1 for _, ok in results if not ok)
print(f'TOTAL {len(results)} tests, {len(results) - n_fail} PASS, {n_fail} FAIL')
sys.exit(1 if n_fail else 0)
