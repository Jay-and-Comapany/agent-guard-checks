#!/usr/bin/env python3
"""guard_irreversible.py — 削除・上書き・外部送信・公開のコマンドを実行する直前に走る検査。

使い方: 実行予定のコマンド文字列を引数か標準入力で渡す。
  python3 guard_irreversible.py "rm -rf build/"
出力(JSON): {"fired": bool, "kinds": [...], "checklist": [...]}
終了コード: 常に0(注入型)。--block を付けると fired 時に 2 を返す。

判定規則(固定):
  1. ヒアドキュメント本文(<<'TAG' ... TAG)と引用文字列("..." '...')を先に除去する。
     誤検知を減らすため照合しない。その結果、bash -c等の引用された実行コードも見逃す。
  2. 残った実行意図部分に対して、
     DESTRUCTIVE: rm -r / rm -f / rmdir / git push --force / git reset --hard / DROP TABLE / truncate / shred
     単純な > リダイレクトによる上書きは検出しない。
     EXTERNAL:    curl/wget の -X POST|PUT|DELETE、mail/sendmail、slack/gh pr create/comment、publish/deploy 系
     LOCK_MASKED: "lock acquire" の結果がパイプで握り潰されている(acquire ... | head 等)
  3. 該当時に4点の確認を注入する: ①対象を1件ずつ中身で判断したか ②復元経路を実証したか ③削除前に記録したか ④対象一覧と件数・除外を数えたか
適用外: 読み取り専用コマンド(ls/cat/grep/curl -s GET)。テスト用の一時ディレクトリ内の削除は誤検知になり得る(その場合は --block を使わない)。
rollback: hooks 設定から外す。状態を持たない。
"""
import sys, re, json

def strip_data(cmd: str) -> str:
    out, i = [], 0
    for m in re.finditer(r"<<-?\s*'?\"?([A-Za-z_][A-Za-z0-9_]*)'?\"?", cmd):
        tag = m.group(1)
        out.append(cmd[i:m.end()])
        end = re.search(rf"^\s*{re.escape(tag)}\s*$", cmd[m.end():], re.M)
        i = m.end() + (end.end() if end else len(cmd) - m.end())
    out.append(cmd[i:])
    s = ''.join(out)
    s = re.sub(r'"(?:[^"\\]|\\.)*"', '""', s)
    s = re.sub(r"'(?:[^'\\]|\\.)*'", "''", s)
    return s

RULES = [
    ('DESTRUCTIVE', re.compile(r'(\brm\s+(-[a-zA-Z]*r[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*)\b|\brmdir\b|git\s+push\s+.*--force|git\s+reset\s+--hard|DROP\s+TABLE|\btruncate\b|\bshred\b)', re.I)),
    ('EXTERNAL', re.compile(r'((curl|wget|http)\b.*-X\s*(POST|PUT|DELETE|PATCH)|\bsendmail\b|\bmail\s+-s|gh\s+(pr|issue)\s+(create|comment|merge)|\bslack\b.*send|\bpublish\b|\bdeploy\b)', re.I)),
    ('LOCK_MASKED', re.compile(r'lock[^|\n]*acquire[^|\n]*\|\s*(head|tail|cat|grep|tee)', re.I)),
]
CHECKLIST = ['①対象を1件ずつ中身で判断したか(名前・件数・経過時間だけで選んでいないか)', '②復元経路を実際に検証したか(「あるはず」は不可)', '③削除・送信の前に記録を残したか', '④対象一覧を出して件数を数え、除外すべきものを明示的に引いたか']

def check(cmd):
    intent = strip_data(cmd)
    kinds = [k for k, rx in RULES if rx.search(intent)]
    return {'fired': bool(kinds), 'kinds': kinds, 'checklist': CHECKLIST if kinds else []}

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--block']
    cmd = ' '.join(args) if args else sys.stdin.read()
    r = check(cmd)
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(2 if (r['fired'] and '--block' in sys.argv) else 0)
