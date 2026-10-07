"""Try a missing-key report using temporary synthetic configuration."""
from pathlib import Path
import tempfile
from envcheck import check, summary

with tempfile.TemporaryDirectory(prefix="envcheck-demo-") as directory:
    folder = Path(directory)
    example, actual = folder / "example.env", folder / "sample.env"
    example.write_text("HOST=\nPORT=\nTOKEN=\n")
    actual.write_text("HOST=localhost\nPORT=\n")
    print(summary(check(example, actual)))
    actual.write_text("HOST=localhost\nPORT=8080\nTOKEN=synthetic-placeholder\n")
    print("\nAfter fixing the synthetic configuration:")
    print(summary(check(example, actual)))
