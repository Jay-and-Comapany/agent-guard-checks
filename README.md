# Four lightweight checks for reviewing Claude Code actions

- These checks return advisory caution text in JSON; they do not block, execute, or modify anything by themselves.
- The default configuration (`settings.example.json`) does not refuse or stop dangerous commands.
- Whether these checks reduce mistakes has not been measured.

[English quickstart: try five completion-check examples offline](QUICKSTART.en.md). No Claude account or paid guide is required.

# agent-guard-checks — AIエージェントの運用を確認するPythonコード4本

依存なし・Python 3.9+・各ファイル1本で完結。コピーして使えます。MIT License。

自分たちで動かしているAIエージェントの運用記録(2026年、人間の訂正が入った場面を型ごとに集計したもの)で、いちばん多かった失敗は **「確認しないまま完了と報告する」** 型でした。**「ルールは書いてあったのに、実行の瞬間に効かなかった」** 型も繰り返し記録されています。この4本は、報告文やコマンドなどを照合し、確認を促すJSONを返すコードです。通常は操作を止めません。`check_completion_claims.py --strict` と `guard_irreversible.py --block` は該当時に終了コード2を返しますが、呼び出し側でその結果を扱う必要があります。

> 正直な注記: 4本の検査が事故を減らす効果は、まだ測定できていません。手元の運用でしばらく走らせている段階で、発火の記録は取れていますが、対照実験はしていません。効果の主張ではなく、「同じ失敗を繰り返している人が、自分の環境で試せる形」として公開します。

## 4本の検査

| ファイル | 走る瞬間 | 止めたい失敗 | 発火条件(固定) |
|---|---|---|---|
| `check_completion_claims.py` | 完了報告を書いた直後 | 検証せずに「できた」と断定する | 完了断定語あり かつ 確かめた痕跡(テスト結果・読み戻し等)なし |
| `guard_irreversible.py` | 削除・上書き・送信・公開コマンドの直前 | 不可逆操作をルール無視で実行する | `rm -r/-f`、`git push --force`、`DROP TABLE`、`curl -X POST/PUT/DELETE`、`publish/deploy`、lock取得結果の握り潰し |
| `capture_correction.py` | 人間の発言が届いた直後 | 訂正・否定・困惑を聞き流す | 否定・不明瞭・「自明」・「端的に」・「〜なし？」・「なんで」・停止指示の語形 |
| `preflight_existing.py` | 「作る・調べる」依頼を受けた直後 | 既にある材料を確認せずに作り始める | 依頼文の識別子がファイル名または先頭2048文字に一致 |

### 6つの型との対応

この4本は、社内の型索引(6つの根本原因型)のうち3つに直接対応します: `check_completion_claims.py`→「検証せずに断定した」、`guard_irreversible.py`→「ルールはあったが行動の瞬間に発火しなかった」、`preflight_existing.py`→「既にある材料を確認せずに動いた」。`capture_correction.py` は人間の訂正反応を拾う仕組みで、「自分の前提を疑わなかった」と「説明が相手に届いていない」の両方にゆるく関係しますが、どちらの正確な対応でもありません。残る1つの型「表層のsignal(名前・件数・見た目)で判断した」には、4本のうちどれも対応していません。

どれも標準入力で本文(発言・コマンド・報告)を受け取り、JSONを標準出力に返します。終了コードは既定では0(注意文を「注入」する型)。`guard_irreversible.py --block` と `check_completion_claims.py --strict` は、そのフラグを付けた場合だけ発火時に終了コード2を返します。状態を持たず、`capture_correction.py --log <path>` を指定した時だけ記録を追記します。

```sh
echo "テストは通ったはずなので完了しました" | python3 check_completion_claims.py
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

AI COMPANY(2026年創業、人間の労働を最小にして実市場で検証する小さな会社)の運用記録から切り出しました。運用記録の集計と、記録のもとになった失敗の型については、noteの無料記事を参照してください（530件は独立した事故数ではなく、訂正・指摘・再発を含む運用観察の集計です）: https://note.com/d_jay0808/n/ne44b3e196f09

質問・反例・「うちではこう失敗した」は Issue へどうぞ。同じ型の失敗が別の環境で出るかどうかを知りたいので、反例ほど歓迎します。

---

**English summary.** Four dependency-free Python checks that return JSON prompts for reviewing: claiming completion without evidence, running irreversible commands, ignoring a human correction, and building something that already exists. Each is a single-file CLI (stdin → JSON), plus a Claude Code hooks adapter (`claude_adapter.py`, `settings.example.json`). Effect on incident rate is **not yet measured**; published so others can try the same checks in their own setup. MIT.

## Comparison (free code / $9 field pack / Anthropic Hookify)

| | Free code (this repo) | $9 field pack | Anthropic Hookify |
|---|---|---|---|
| **What it does** | 4 dependency-free Python CLI checks (completion-claim, irreversible-command, correction-capture, existing-material preflight) plus a Claude Code hooks adapter; each returns a JSON advisory, and three of the four are wired by default in `settings.example.json`. | The identical 4 checks and adapter, byte-verified against this repo, plus an English guide: what each check does and does not catch, the exact Claude Code hook wiring, a budget-capped isolated test procedure, and the six failure types behind these checks (one of which, "judged by surface signals," has no corresponding check). | A Claude Code plugin that turns markdown+YAML rule files into hooks. Its `/hookify` command drafts a rule from an explicit instruction, or by scanning recent chat for behavior you corrected. |
| **What it does not do** | Not a security boundary: always exits 0 unless the flag a given check supports (`--strict` on completion claims, `--block` on irreversible commands) is set, which `settings.example.json` does not set. Misses command text inside quotes/heredocs and plain `>` overwrites. | Does not change runtime behavior or add checks — same code as the free repo above. Covers the current guide and packaging only; future updates, if any, are not included in the purchase commitment. | Default rule action is `warn` (allows the operation); `block` is opt-in per rule and, per its own docs, only prevents execution on `PreToolUse` or stops the session on `Stop`. No rules ship pre-installed — each is written by hand or drafted via `/hookify`. |
| **Dependencies** | Python 3 standard library only — no third-party packages. | Same as the free code; the guide also assumes a working Claude Code install to follow the wiring steps. | Claude Code itself, installed as a plugin via the Claude Code Marketplace. Python 3.7+ with no external dependencies for its own rule matching, per its README. |
| **Cost** | $0. MIT license. | $9 USD, one time, for the current guide and packaging (confirmed on the live store page). The code inside is the same free MIT code. | $0 to install. Its license is unclear: the plugin's own README says "MIT License", but the repository's top-level `LICENSE.md` says all rights reserved, subject to Anthropic's Commercial Terms of Service — neither the plugin's metadata nor the marketplace listing states a license. We could not resolve this conflict from primary sources. |
| **Where to get it** | github.com/Jay-and-Comapany/agent-guard-checks | jayworks7.gumroad.com/l/agent-guard-field-pack | Bundled with Claude Code: github.com/anthropics/claude-code/tree/main/plugins/hookify |

**Sources (fetched 2026-09-10).** Free code and $9 pack: this repository's `README.md`, `LICENSE`, `settings.example.json`, and the four checks' own docstrings, plus the live Gumroad page. Anthropic Hookify: `github.com/anthropics/claude-code/blob/main/plugins/hookify/README.md`, its `plugin.json`, the repo's `.claude-plugin/marketplace.json`, and the repo's `LICENSE.md`. None of the three publishes measured incident-reduction data that we could find; popularity is not covered by this table.

**English field guide (optional, US$9).** The code above is free and stays free under MIT. If you want the English guide that explains what each check does and does not catch, the exact Claude Code hooks wiring, and how to test the setup in an isolated session before it touches your real settings, it is sold as a zip on Gumroad: https://jayworks7.gumroad.com/l/agent-guard-field-pack — the guide was written by an AI (Claude) and says so inside, and whether these checks reduce mistakes has not been measured.
