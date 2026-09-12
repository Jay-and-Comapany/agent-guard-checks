# Try the completion check offline

This walkthrough uses one of the four free checks: `check_completion_claims.py`.
It looks for completion words and evidence-like text in a report. It does **not**
verify that a deployment, test, or other action actually happened. It is not a
security boundary, and its effect on mistakes has not been measured.

AI-written documentation by AI-D for Jay. The five examples below were executed
against code at commit `e78398e93a45f05ab31ed11479ca583e3ae9903e` on 2026-09-12.
The reports are synthetic strings, not records of real deployments.

## Get the code

Use Python 3.9+ and Git in a POSIX-compatible shell (for example, macOS Terminal).
Run the following in a directory where `agent-guard-checks` does not already exist:

```sh
git clone https://github.com/Jay-and-Comapany/agent-guard-checks.git
cd agent-guard-checks
git checkout --detach e78398e93a45f05ab31ed11479ca583e3ae9903e
```

The clone needs internet access. The checks below run locally using Python's
standard library: no API key, Claude account, package installation, or purchase.
They do not install hooks or change your agent settings.

## First example

```sh
printf '%s\n' 'Deployment completed.' | python3 -B check_completion_claims.py
```

The JSON contains `"fired": true`, `"claims": ["completed"]`, and
`"evidence": []`. The `advice` field is Japanese; when fired, it asks for actual
verification details or an explicit statement that the result is unverified.
The default exit status is **0 even when fired**.

To make this check return status 2 when fired:

```sh
printf '%s\n' 'Deployment completed.' | python3 -B check_completion_claims.py --strict
```

This does not block a deployment by itself. A caller must inspect and enforce
the exit status. A shell running with `set -e` may exit at this deliberate status 2.

## Five observed results

Feed each report to the same command, using `--strict` only in row 2.

| Report text | Mode | `fired` | Exit status |
|---|---|---|---|
| `Deployment completed.` | Default | `true` | 0 |
| `Deployment completed.` | `--strict` | `true` | 2 |
| `Deployment completed; verified by 3/3 tests, exit 0.` | Default | `false` | 0 |
| `Deployment completed. Compass integration is next.` | Default | `false` | 0 |
| `Deployment is not completed.` | Default | `false` | 0 |

Row 3 matches `verified`, `3/3`, and `exit 0`. Those are only words in the input;
the checker does not run tests or authenticate evidence. Do not add such words
just to silence it.

Row 4 is a **known false negative**: the case-insensitive `PASS` expression also
matches `pass` inside `Compass`. There is no word boundary around that expression.
The completion claim therefore goes unflagged despite having no real evidence.

Row 5 suppresses the completion claim because of its recognized negation.
Negation is checked per sentence; evidence-like matches are collected across
the whole input. The code does not link each claim to its own evidence, understand
all negations, or determine whether any claim is true. `fired: false` is not approval.

## Try a report from your own workflow

After reviewing the source, pass a local plain-text report on standard input:

```sh
python3 -B check_completion_claims.py < /path/to/report.txt
```

Replace the path with an existing report. This command reads that file and prints
JSON; it does not modify the report or send it to a model. Review the actual test
output or resulting state separately. Start without `--strict` to see which
phrases the heuristic catches and misses before deciding whether to integrate it.

If you want to report a false positive or missed claim, open an
[issue](https://github.com/Jay-and-Comapany/agent-guard-checks/issues) with a short,
invented example, the code version, expected result, and actual JSON. Do not post
customer data, credentials, or private logs.

The [README](README.md) covers the other checks, optional hook integration, and
optional paid explanatory material. All code needed for this walkthrough is free
under the repository's [MIT license](LICENSE).
