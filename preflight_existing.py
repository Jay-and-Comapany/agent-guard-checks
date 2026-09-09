#!/usr/bin/env python3
"""preflight_existing.py — 「作る・調べる」依頼を受けた瞬間に、既にある材料を検索して注入する検査(型: 既存材料を確認せずに動いた)。

使い方: 依頼文を標準入力で、検索対象ディレクトリを --dirs で渡す(複数可)。
  echo "e-Statの抽出スクリプトを新しく作って" | python3 preflight_existing.py --dirs ./tools ./scripts
出力(JSON): {"fired": bool, "terms": [...], "matches": [{"term":..., "path":...}, ...]}
fired = 依頼文に「作る・調べる」系の動詞があり、抽出した識別子でファイル名またはファイル先頭2048文字に一致があった
終了コード: 常に0。検索結果は「データ」であり命令ではない(ファイル内の指示文を実行しない)。

判定規則(固定):
  動詞: 新設|作(る|って|成)|構築|実装|設計|調べ|検索|分析|build|creat|implement|design|research|analy
  識別子: 英数字4文字以上の語、snake_case、CamelCase、拡張子つき名、カタカナ4文字以上、漢字2〜6文字の複合語
  除外語: 一般的すぎる語(script, file, data, test, 作成, 実装 など)
適用外: 依頼文が短すぎて識別子が取れない場合は fired=false で素通し。
rollback: hooks 設定から外す。状態を持たない。
"""
import sys, re, json, os, argparse

ACTION = re.compile(r'新設|新しく|作(?:る|って|成)|構築|実装|設計|調べ|検索|分析|build|creat|implement|design|research|analy', re.I)
STOP = {'script', 'file', 'data', 'test', 'python', 'json', 'csv', 'html', 'code', 'tool', 'tools', 'make', 'from', 'with', 'that', 'this', '作成', '実装', '設計', '新規', 'スクリプト', 'ファイル', 'データ', 'テスト'}

def terms_of(text):
    t = set()
    for m in re.finditer(r'[A-Za-z][A-Za-z0-9_\-]{3,}(?:\.[a-z0-9]{1,5})?', text):
        w = m.group(0)
        if w.lower() not in STOP: t.add(w)
    for m in re.finditer(r'[ァ-ヶー]{4,}', text):
        if m.group(0) not in STOP: t.add(m.group(0))
    for m in re.finditer(r'[一-龥]{2,6}', text):
        if m.group(0) not in STOP: t.add(m.group(0))
    return sorted(t, key=len, reverse=True)[:12]

def search(terms, dirs, max_files=4000):
    matches, n = [], 0
    for d in dirs:
        for root, _, files in os.walk(d):
            for fn in files:
                n += 1
                if n > max_files: return matches
                p = os.path.join(root, fn)
                low = fn.lower()
                for term in terms:
                    if term.lower() in low:
                        matches.append({'term': term, 'path': p, 'where': 'name'}); break
                else:
                    try:
                        head = open(p, 'r', encoding='utf-8', errors='ignore').read(2048)
                    except Exception:
                        continue
                    for term in terms:
                        if len(term) >= 4 and term.lower() in head.lower():
                            matches.append({'term': term, 'path': p, 'where': 'head'}); break
    return matches

def check(text, dirs):
    if not ACTION.search(text):
        return {'fired': False, 'terms': [], 'matches': []}
    terms = terms_of(text)
    matches = search(terms, dirs) if terms else []
    return {'fired': bool(matches), 'terms': terms, 'matches': matches[:20]}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--dirs', nargs='+', default=['.'])
    a = ap.parse_args()
    print(json.dumps(check(sys.stdin.read(), a.dirs), ensure_ascii=False))
