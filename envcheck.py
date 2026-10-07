"""Check .env keys against an example without printing their values."""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

VERSION = "0.1.0"
MAX_BYTES = 1024 * 1024
KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def _value(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if text[0] in ("'", '"'):
        quote = text[0]
        escaped = False
        for index, char in enumerate(text[1:], 1):
            if char == quote and not escaped:
                rest = text[index + 1:].strip()
                if rest and not rest.startswith("#"):
                    raise ValueError("Unexpected text after quoted value.")
                return text[1:index]
            escaped = char == "\\" and not escaped
        raise ValueError("Quoted value must close on the same line.")
    for index, char in enumerate(text):
        if char == "#" and (index == 0 or text[index - 1].isspace()):
            return text[:index].rstrip()
    return text


def parse_env(path: str | Path) -> dict:
    """Return key names, line numbers and emptiness only; no values in results."""
    path = Path(path)
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Configuration file exceeds the 1 MiB limit.")
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("Configuration file must use UTF-8 text.") from None
    keys, errors, occurrences = {}, [], {}
    for line_number, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export ") or line.startswith("export\t"):
            line = line[6:].lstrip()
        if "=" not in line:
            errors.append({"line": line_number, "detail": "Expected KEY=value assignment."})
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not KEY.fullmatch(key):
            errors.append({"line": line_number, "detail": "Invalid environment key name."})
            continue
        occurrences.setdefault(key, []).append(line_number)
        try:
            parsed = _value(value)
        except ValueError as error:
            errors.append({"line": line_number, "key": key, "detail": str(error)})
            continue
        keys[key] = {"line": line_number, "empty": not parsed.strip()}
    return {
        "path": str(path), "keys": keys, "errors": errors,
        "duplicates": [{"key": key, "lines": lines} for key, lines in sorted(occurrences.items()) if len(lines) > 1],
    }


def check(example: str | Path, actual: str | Path, *, strict: bool = False) -> dict:
    expected, supplied = parse_env(example), parse_env(actual)
    names, present = set(expected["keys"]), set(supplied["keys"])
    missing, extra = sorted(names - present), sorted(present - names)
    empty = sorted(key for key, info in supplied["keys"].items() if info["empty"])
    problems = bool(missing or empty or expected["errors"] or supplied["errors"] or expected["duplicates"] or supplied["duplicates"] or (strict and extra))
    return {"format": "envcheck/v1", "version": VERSION, "ok": not problems, "strict": strict,
            "example": expected, "actual": supplied, "missing": missing, "empty": empty, "extra": extra}


def summary(report: dict) -> str:
    lines = ["EnvCheck — " + ("configuration keys pass" if report["ok"] else "configuration needs attention")]
    for label, name in (("Missing", "missing"), ("Empty", "empty"), ("Extra", "extra")):
        if report[name]:
            lines.append(label + ": " + ", ".join(report[name]))
    for label in ("example", "actual"):
        for duplicate in report[label]["duplicates"]:
            lines.append(f"Duplicate {label} key: {duplicate['key']} (lines {', '.join(map(str, duplicate['lines']))})")
        for error in report[label]["errors"]:
            lines.append(f"Invalid {label} line {error['line']}: {error['detail']}")
    lines.append("Values are omitted. No interpolation, execution or network requests.")
    return "\n".join(lines)


def save_report(report: dict, output: str | Path, inputs=()) -> None:
    output = Path(output)
    if output.suffix.lower() != ".json" or output.is_symlink():
        raise ValueError("Choose a .json output that is not a symbolic link.")
    if any(output.resolve() == Path(item).resolve() for item in inputs):
        raise ValueError("Report output cannot replace an input configuration.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, prefix=".envcheck-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", type=Path, help="Expected key template, such as .env.example")
    parser.add_argument("actual", type=Path, help="Configuration to check, such as .env")
    parser.add_argument("--strict", action="store_true", help="Treat extra keys as failures too")
    parser.add_argument("--json", action="store_true", help="Print a JSON report without values")
    parser.add_argument("--output", type=Path, help="Save a .json report; replaces an existing report")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()
    try:
        report = check(args.example, args.actual, strict=args.strict)
        if args.output:
            save_report(report, args.output, (args.example, args.actual))
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2) if args.json else summary(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
