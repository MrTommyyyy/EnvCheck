"""Check the packaged CLI using only temporary synthetic inputs."""
import json
from pathlib import Path
import subprocess
import tempfile

EXE = Path("dist/EnvCheck.exe").resolve()
def run(*args, code=0):
    result = subprocess.run([str(EXE), *map(str, args)], capture_output=True, text=True, timeout=60)
    assert result.returncode == code, (result.returncode, result.stdout, result.stderr)
    assert "synthetic-private-value" not in result.stdout + result.stderr
    return result.stdout

assert run("--version").strip() == "0.1.0"
with tempfile.TemporaryDirectory() as directory:
    folder = Path(directory)
    example, actual = folder / "example.env", folder / "actual.env"
    example.write_text("HOST=\nTOKEN=\n")
    actual.write_text("HOST=local\nTOKEN=synthetic-private-value\n")
    assert json.loads(run(example, actual, "--json"))["ok"]
    actual.write_text("HOST=\nHOST=local\n")
    report = folder / "report.json"
    run(example, actual, "--output", report, code=1)
    assert json.loads(report.read_text())["missing"] == ["TOKEN"]
    run(example, folder / "missing", code=2)
print("Packaged EnvCheck configuration and redaction checks passed")
