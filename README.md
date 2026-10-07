# EnvCheck

Check a project's `.env` configuration against its example before a confusing startup failure. EnvCheck finds **missing keys, empty assignments, duplicate keys and malformed lines**. Configuration values never appear in its reports or normal error messages.

Version **0.1.0** · Python **3.11+** · MIT · standard library only

[Download](https://github.com/MrTommyyyy/EnvCheck/releases/latest) · [Report an issue](https://github.com/MrTommyyyy/EnvCheck/issues)

![Tests](https://github.com/MrTommyyyy/EnvCheck/actions/workflows/tests.yml/badge.svg)

## Why this exists

Setting up a project should not mean hunting for a missing configuration key after the app crashes. I want a small check that can run locally or in CI, explain what needs fixing and avoid putting secrets into logs.

## Try it

```sh
python envcheck.py example.env sample.env
python envcheck.py .env.example .env --strict
python envcheck.py .env.example .env --json --output env-report.json
```

`example.env` and `sample.env` are public synthetic examples. The sample intentionally misses `DATABASE_URL` and repeats `PORT`, so its check exits with a finding. No real credentials are included.

Example output:

```text
EnvCheck — configuration needs attention
Missing: DATABASE_URL
Duplicate actual key: PORT (lines 3, 4)
Values are omitted. No interpolation, execution or network requests.
```

## Windows executable

Download `EnvCheck-0.1.0-Windows-x64.zip`, extract it and open a terminal in that folder:

```powershell
.\EnvCheck.exe "C:\project\.env.example" "C:\project\.env" --strict
```

Python is bundled in that download. This is a **terminal application**; double-clicking it without arguments is not the intended way to run it. The source ZIP works with Python on Windows, macOS and Linux.

## Checks and exit codes

| Result | Behaviour |
| --- | --- |
| Missing or empty actual key | Finding; exit `1` |
| Repeated key in either file | Finding, including line numbers; exit `1` |
| Malformed assignment or quoted value | Finding with a line number; original line omitted |
| Extra actual key | Listed; only fails with `--strict` |
| Valid configuration | Exit `0` |
| Missing/unreadable input, bad encoding or output failure | Exit `2` |

Template values may be empty; only the key names define what is required. Empty actual values, including whitespace-only values, fail. Comparisons are case-sensitive. Duplicate keys fail even when their assignments agree; the parser records the last valid assignment for the other checks.

`--output` requires a `.json` path. Existing reports are replaced atomically; a failed write preserves the previous report. An input configuration and symbolic-link output cannot be used as the destination.

## Supported syntax and limits

- UTF-8, with an optional BOM; files up to 1 MiB.
- `KEY=value`, optional spaces around `=`, and optional `export` prefixes.
- Key names use ASCII letters, numbers and underscores, starting with a letter or underscore.
- Single-line single-quoted or double-quoted values, blank lines and comments.
- For unquoted values, `#` begins a comment at the start of the value or after whitespace. Inside quotes it stays part of the value.
- Backslashes can escape closing quotes for syntax recognition; escape sequences are not interpreted.

This deliberately implements a small syntax subset. Multiline quoted values, interpolation and shell expansion are unsupported. EnvCheck does not load variables into the process or decide whether a URL, token, port or credential is valid. A non-empty placeholder passes the presence check. It does not read your process environment.

The tool reads values in memory to determine emptiness but omits them from output. Reports still include **key names, filenames and line numbers**, which can reveal project details. Review reports before sharing. No network requests or project code execution.

## CI

```yaml
- name: Check configuration keys
  run: python envcheck.py .env.example .env --strict
```

Provide the configuration through your existing CI setup. Do not commit real `.env` files or secrets just to use this tool.

## Development

```sh
python -m unittest discover -s tests -v
```

Ten tests cover redacted output, parsing, missing/empty keys, duplicates, input limits, protected exports and real CLI exit codes. CI runs on Windows, macOS and Linux. Windows release builds also exercise the packaged executable with disposable files.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md). Licensed under [MIT](LICENSE).
