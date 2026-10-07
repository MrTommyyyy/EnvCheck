import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from envcheck import check, parse_env, save_report, summary


class EnvTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.example, self.actual = self.folder / "example.env", self.folder / "local.env"
        self.example.write_text("HOST=\nPORT=\nTOKEN=\n", encoding="utf-8")
        self.actual.write_text("HOST=localhost\nPORT=8080\nTOKEN=not-a-real-secret\n", encoding="utf-8")

    def test_matching_keys_and_never_return_values(self):
        report = check(self.example, self.actual)
        self.assertTrue(report["ok"])
        for output in (json.dumps(report), summary(report), repr(parse_env(self.actual))):
            self.assertNotIn("not-a-real-secret", output)
            self.assertNotIn("localhost", output)

    def test_missing_empty_and_extras_with_strict_mode(self):
        self.actual.write_text("HOST=\nPORT='  '\nOTHER=value\n")
        report = check(self.example, self.actual)
        self.assertEqual(report["missing"], ["TOKEN"])
        self.assertEqual(report["empty"], ["HOST", "PORT"])
        self.assertEqual(report["extra"], ["OTHER"])
        self.assertFalse(report["ok"])
        self.actual.write_text("HOST=a\nPORT=1\nTOKEN=b\nOTHER=c\n")
        self.assertTrue(check(self.example, self.actual)["ok"])
        self.assertFalse(check(self.example, self.actual, strict=True)["ok"])

    def test_comments_quotes_export_crlf_and_bom(self):
        self.actual.write_bytes(b"\xef\xbb\xbf# comment\r\nexport HOST = 'local#host' # note\r\nPORT=8080 # note\r\nTOKEN=\"secret # text\"\r\n")
        self.assertTrue(check(self.example, self.actual)["ok"])
        self.assertEqual(parse_env(self.actual)["keys"]["TOKEN"]["line"], 4)

    def test_duplicate_line_numbers_and_template_duplicates_fail(self):
        self.actual.write_text("HOST=a\nHOST=b\nPORT=1\nTOKEN=c\n")
        report = check(self.example, self.actual)
        self.assertEqual(report["actual"]["duplicates"], [{"key": "HOST", "lines": [1, 2]}])
        self.assertFalse(report["ok"])
        self.example.write_text("HOST=\nHOST=\n")
        self.assertFalse(check(self.example, self.actual)["ok"])

    def test_malformed_values_report_locations_without_payload(self):
        self.actual.write_text('bad-secret-key\nBAD.KEY=hidden-secret\nTOKEN="unclosed-secret\nHOST="ok" trailing-secret\n')
        report = check(self.example, self.actual)
        self.assertEqual(len(report["actual"]["errors"]), 4)
        self.assertNotIn("secret", json.dumps(report))
        self.assertFalse(report["ok"])

    def test_interpolation_is_never_executed(self):
        self.actual.write_text('HOST=$(touch forbidden)\nPORT=${PORT}\nTOKEN=`whoami`\n')
        self.assertTrue(check(self.example, self.actual)["ok"])
        self.assertFalse((self.folder / "forbidden").exists())

    def test_size_limit_and_utf8_errors_do_not_leak_bytes(self):
        with patch("envcheck.MAX_BYTES", 4):
            with self.assertRaisesRegex(ValueError, "limit"):
                parse_env(self.actual)
        self.actual.write_bytes(b"TOKEN=\xffprivate")
        with self.assertRaisesRegex(ValueError, "UTF-8") as error:
            parse_env(self.actual)
        self.assertNotIn("private", str(error.exception))

    def test_atomic_save_preserves_existing_report_on_encoding_failure(self):
        output = self.folder / "report.json"
        output.write_text("previous report")
        with patch("envcheck.json.dump", side_effect=ValueError("simulated failure")):
            with self.assertRaises(ValueError):
                save_report(check(self.example, self.actual), output)
        self.assertEqual(output.read_text(), "previous report")
        self.assertEqual(list(self.folder.glob(".envcheck-*")), [])

    def test_output_cannot_replace_input_or_symlink_target(self):
        input_json = self.folder / "input.json"
        input_json.write_text("TOKEN=synthetic")
        with self.assertRaises(ValueError):
            save_report({}, input_json, [input_json])
        self.assertEqual(input_json.read_text(), "TOKEN=synthetic")
        link = self.folder / "link.json"
        try:
            link.symlink_to(self.actual)
        except OSError:
            return
        with self.assertRaises(ValueError):
            save_report({}, link)

    def test_cli_real_inputs_exit_codes_and_json(self):
        script = Path(__file__).resolve().parents[1] / "envcheck.py"
        def run(*args):
            return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)
        result = run(self.example, self.actual, "--json")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(json.loads(result.stdout)["ok"])
        self.assertNotIn("not-a-real-secret", result.stdout + result.stderr)
        self.actual.write_text("HOST=\n")
        self.assertEqual(run(self.example, self.actual).returncode, 1)
        self.assertEqual(run(self.example, self.folder / "missing").returncode, 2)


if __name__ == "__main__":
    unittest.main()
