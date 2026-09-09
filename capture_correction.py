#!/usr/bin/env python3
"""capture_correction.py — 人間の発言が届いた瞬間に「訂正・否定・困惑」の形を捕まえ、記録に落とす検査。

使い方: 人間の発言を標準入力で渡す。--log <path> で JSONL に追記(省略時は標準出力のみ)。
  echo "違う、そういう意味じゃない" | python3 capture_correction.py --log corrections.jsonl
出力(JSON): {"fired": bool, "kinds": [...], "prompt": str}
fired 時の prompt は「何の期待とズレたのかを一文で言語化せよ」という自己記録の指示文。
終了コード: 常に0。

目的: 訂正の記録を思い出すための注意文を、発言の到着時に返す。
記録率の改善は未検証。
判定規則(固定): 否定 / 不明瞭 / 聞くべきでない質問 / 説明が過剰 / 選択肢の見落とし / 前提への異議 / 停止指示
適用外: 引用文・第三者の発言の転記。誤検知のコストは注意書き1行なので広めに取る。
rollback: hooks 設定から外す。ログファイルは残る(削除は人間の判断)。
"""
import sys, re, json, datetime

PATTERNS = [
    (r'じゃない|ではない|違いま|違う|ちがう|\bno\b[, ]|that\'s not|not what I', '否定'),
    (r'わからな|分からな|わかりにく|分かりにく|難し(い|くて)|unclear|confus', '不明瞭'),
    (r'自明|当然|当たり前|言うまでもな|obviously', '聞くべきでない質問をした'),
    (r'端的に|簡潔に|短く|長い|冗長|too long|shorter', '説明が過剰'),
    (r'なし[？?]|ないの[？?]|ないんですか|できない[？?]|できないの|why not', '選択肢の見落としを指摘された'),
    (r'なんで|なぜ.*の[？?]|そもそも|前提|本当に[？?]|why (do|did|are) you', '前提への異議'),
    (r'止め|やめ|stop\b|待って|wait\b', '停止指示'),
]

def check(text):
    kinds = [k for rx, k in PATTERNS if re.search(rx, text, re.I)]
    prompt = ''
    if kinds:
        prompt = ('【違和感の検出: ' + ' / '.join(kinds) + '】相手が何を期待していて、実際に何が出てきたのかを「○○だと思っていたが、実際は△△だった」の形で一文にし、'
                  '同じ形の失敗が今後も起きるなら型として記録する。謝罪や自己批判は不要。次に同じことが起きない仕組みだけを書く。')
    return {'fired': bool(kinds), 'kinds': kinds, 'prompt': prompt}

if __name__ == '__main__':
    text = sys.stdin.read()
    r = check(text)
    if '--log' in sys.argv and r['fired']:
        path = sys.argv[sys.argv.index('--log') + 1]
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'ts': datetime.datetime.now().isoformat(timespec='seconds'), 'kinds': r['kinds'], 'snippet': text.strip()[:120]}, ensure_ascii=False) + '\n')
    print(json.dumps(r, ensure_ascii=False))
