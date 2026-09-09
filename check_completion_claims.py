#!/usr/bin/env python3
"""check_completion_claims.py — 完了報告の直前に走る検査(型: 検証せずに断定した)。

使い方: 報告文を標準入力で渡す。
  echo "修正しました。テストは3/3 PASSです" | python3 check_completion_claims.py
出力(JSON): {"fired": bool, "claims": [...], "evidence": [...], "advice": str}
終了コード: 常に0(注入型)。--strict を付けると fired 時に 2 を返す(CI向け)。

判定規則(固定):
  claim  = 完了を断定する語(完了しました/できました/対応済み/直しました/公開しました/done/completed/fixed/published)
  evidence = 確かめた痕跡(実測/read-back/読み戻し/exit 0/PASS/件中/SHA/hash/%/tested/verified/差分0/一致)
  fired = claim あり かつ evidence なし
偽陽性を減らす規則: 句点・改行などで分割し、否定語のある文のclaimを除外する。別文の否定語では抑制しない。同一文の複数主張や否定のかかり先は解析しない。
適用外: 会話の雑談・計画文(まだ何もしていない文)。誤検知したら --strict を外し、注入文だけにする。
rollback: このファイルを hooks 設定から外すだけ。状態を持たない。
"""
import sys, re, json

CLAIM = re.compile(r'(完了しました|完了した|できました|対応済み|修正しました|直しました|公開しました|保存しました|送信しました|実装しました|\bdone\b|\bcompleted\b|\bfixed\b|\bpublished\b|\bimplemented\b)', re.I)
NEGATED = re.compile(r'(しませんでした|未完了|できていません|できませんでした|not (done|completed|fixed)|まだ|していません)', re.I)
EVIDENCE = re.compile(r'(実測|read-?back|読み戻し|exit (code )?0|PASS|件中|\d+/\d+|SHA-?256|hash|\d+%|tested|verified|検証済み\(|差分0|不一致0(?!\d)|(?<!不)一致|確認済み\(|測定|date実測)', re.I)

def check(text):
    sentences = re.split(r'[。！？!?\n]|(?<=[a-zA-Z])\.(?:\s|$)', text)
    claims = [m.group(0) for sentence in sentences if not NEGATED.search(sentence)
              for m in CLAIM.finditer(sentence)]
    negated = bool(NEGATED.search(text))
    evidence = [m.group(0) for m in EVIDENCE.finditer(text)]
    fired = bool(claims) and not evidence
    advice = ''
    if fired:
        advice = '完了を断定する語があるのに、確かめた痕跡(実測値・読み戻し・テスト結果・件数・hash)が本文にない。何をどう確かめたかを1行足すか、「未検証」と書く。'
    return {'fired': fired, 'claims': claims[:5], 'evidence': evidence[:5], 'negated': negated, 'advice': advice}

if __name__ == '__main__':
    text = sys.stdin.read()
    r = check(text)
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(2 if (r['fired'] and '--strict' in sys.argv) else 0)
