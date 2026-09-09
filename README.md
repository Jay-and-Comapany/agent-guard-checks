# agent-guard-checks — AIエージェントを「行動の直前」に一度止める検査4本

依存なし・Python 3.9+・各ファイル1本で完結。コピーして使えます。MIT License。

自分たちで動かしているAIエージェントの運用記録(2026年、人間の訂正が入った場面を型ごとに集計したもの)で、いちばん多かった失敗は **「確認しないまま完了と報告する」** 型でした。次いで多いのが **「ルールは書いてあったのに、実行の瞬間に効かなかった」** 型です。ルール文を増やしても行動は変わらなかったので、**行動の直前に外側から一度止める検査**として切り出したのがこの4本です。

> 正直な注記: 4本の検査が事故を減らす効果は、まだ測定できていません。手元の運用でしばらく走らせている段階で、発火の記録は取れていますが、対照実験はしていません。効果の主張ではなく、「同じ失敗を繰り返している人が、自分の環境で試せる形」として公開します。

## 4本の検査

| ファイル | 走る瞬間 | 止めたい失敗 | 発火条件(固定) |
|---|---|---|---|
| `check_completion_claims.py` | 完了報告を書いた直後 | 検証せずに「できた」と断定する | 完了断定語あり かつ 確かめた痕跡(テスト結果・読み戻し等)なし |
| `guard_irreversible.py` | 削除・上書き・送信・公開コマンドの直前 | 不可逆操作をルール無視で実行する | `rm -r/-f`、`git push --force`、`DROP TABLE`、`curl -X POST/PUT/DELETE`、`publish/deploy`、lock取得結果の握り潰し |
| `capture_correction.py` | 人間の発言が届いた直後 | 訂正・否定・困惑を聞き流す | 否定・不明瞭・「自明」・「端的に」・「〜なし？」・「なんで」・停止指示の語形 |
| `preflight_existing.py` | 「作る・調べる」依頼を受けた直後 | 既にある材料を確認せずに作り始める | 依頼文の識別子がファイル名または先頭2048文字に一致 |

どれも標準入力で本文(発言・コマンド・報告)を受け取り、JSONを標準出力に返します。終了コードは常に0(注意文を「注入」する型)。`guard_irreversible.py --block` だけは発火時に終了コード2を返します。状態を持たず、`capture_correction.py --log <path>` を指定した時だけ記録を追記します。

```sh
echo "テストは通ったはずなので完了です" | python3 check_completion_claims.py
python3 guard_irreversible.py "rm -rf build/ && git push --force"
echo "違う、そういう意味じゃない" | python3 capture_correction.py
echo "e-Statの抽出スクリプトを新しく作って" | python3 preflight_existing.py --dirs ./tools
python3 run_tests.py          # 4本の単体試験(18件)
python3 -m unittest test_claude_adapter   # アダプターの試験(12件)
```

## Claude Code に接続する

Claude Code の hooks はイベントJSONを渡すので、単体CLIを直接登録せず `claude_adapter.py` を登録します。`settings.example.json` の絶対パスをこのフォルダーの場所に置き換え、`.claude/settings.json`(プロジェクト)か `~/.claude/settings.json`(ユーザー)に入れてください。公式仕様: https://code.claude.com/docs/en/hooks

- `UserPromptSubmit`: 訂正の捕捉(+ `--dirs /abs/path` を付けた時だけ既存材料の検索)
- `PreToolUse`(matcher `Bash`): 不可逆コマンドの直前に4点の確認を注入
- `Stop`: 完了報告に検証の痕跡がなければ注意文を返す(`stop_hook_active=true` では空を返して連続実行を避ける)

アダプターはコマンド実行も永続ログ記録もしません。不正なJSONは終了コード1(nonblocking)で通知するだけで、権限の許可・拒否は返しません。**セキュリティ境界ではなく、注意文を届ける仕組みです。**

まず隔離した設定で試すなら:
```sh
claude -p --setting-sources '' --settings ./settings.example.json \
  --tools '' --mcp-config '{"mcpServers":{}}' --strict-mcp-config \
  --no-session-persistence --permission-mode dontAsk --max-budget-usd 0.10 \
  --output-format stream-json --verbose --include-hook-events "rm -rf build/ を実行して"
```

他のエージェント基盤(Codex CLI、Cursor、独自ループ)では、同じ4本のCLIを対応するフックから呼び出してください。接続の実装は各基盤で別途必要です。

## 適用外・誤検知・戻し方

- 読み取り専用コマンド(ls/cat/grep/curl GET)は対象外。ヒアドキュメント本文と引用文字列は照合前に除去するため、`bash -c "..."` の中身は見逃します。単純な `>` リダイレクトの上書きも検出しません。
- 完了語の検査は「否定形(まだできていない)」「痕跡つき(3/3 PASS)」では発火しません。誤検知のコストは注意書き1行なので、判定は広めに取っています。
- 戻し方: hooks 設定から外すだけ。状態ファイルはありません(`--log` で作ったJSONLは残るので、消すかどうかは人が決めます)。

## 解説教材（任意・980円）

このリポジトリのコードは、教材を購入せずMITライセンスで利用できます。

AIエージェントの運用記録から30事例を選び、確認手順と検査の選び方をまとめた[日本語教材をnoteで販売しています](https://note.com/d_jay0808/n/n0cd687500dc9)。AIが執筆・編集した教材で、価格は980円。無料部分で3事例とコード1本を確認できます。検査による事故削減効果は未測定です。

## 由来

AI COMPANY(2026年創業、人間の労働を最小にして実市場で検証する小さな会社)の運用記録から切り出しました。運用記録の集計と、記録のもとになった失敗の型については、noteの記事「AIエージェントの失敗530件を型ごとに数えてわかったこと(仕事に入れて困っている人向け)」を参照してください: https://note.com/d_jay0808/n/ne44b3e196f09

質問・反例・「うちではこう失敗した」は Issue へどうぞ。同じ型の失敗が別の環境で出るかどうかを知りたいので、反例ほど歓迎します。

---

**English summary.** Four dependency-free Python checks that stop an AI agent right before the moment it usually fails: claiming completion without evidence, running irreversible commands, ignoring a human correction, and building something that already exists. Each is a single-file CLI (stdin → JSON), plus a Claude Code hooks adapter (`claude_adapter.py`, `settings.example.json`). Effect on incident rate is **not yet measured**; published so others can try the same checks in their own setup. MIT.
