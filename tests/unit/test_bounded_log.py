#!/usr/bin/env python3
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "bounded-log.py"


class BoundedLogTest(unittest.TestCase):
    def run_helper(
        self, output: pathlib.Path, maximum: int, payload: bytes, exit_code: int = 0
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(HELPER),
                "--output",
                str(output),
                "--max-bytes",
                str(maximum),
                "--",
                sys.executable,
                "-c",
                (
                    "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()); "
                    "raise SystemExit(int(sys.argv[1]))"
                ),
                str(exit_code),
            ],
            input=payload,
            check=False,
        )

    def test_preserves_small_output_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "output.log"
            result = self.run_helper(output, 128, b"PX4 startup\n")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b"PX4 startup\n")

    def test_bounds_large_output_and_preserves_both_ends(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "output.log"
            payload = (
                b"first-diagnostic\n"
                + (b"x" * (2 * 1024 * 1024))
                + b"\nlast-diagnostic\n"
            )
            result = self.run_helper(output, 128, payload)
            self.assertEqual(result.returncode, 0)

            captured = output.read_bytes()
            self.assertLessEqual(len(captured), 128)
            self.assertTrue(captured.startswith(b"first-diagnostic\n"))
            self.assertIn(
                b"[output truncated; retaining first and last diagnostics]",
                captured,
            )
            self.assertTrue(captured.endswith(b"\nlast-diagnostic\n"))

    def test_preserves_child_failure_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "output.log"
            result = self.run_helper(output, 128, b"client failed\n", exit_code=23)
            self.assertEqual(result.returncode, 23)
            self.assertEqual(output.read_bytes(), b"client failed\n")

    def test_normalizes_signal_terminated_child_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "output.log"
            result = subprocess.run(
                [
                    sys.executable,
                    str(HELPER),
                    "--output",
                    str(output),
                    "--max-bytes",
                    "128",
                    "--",
                    sys.executable,
                    "-c",
                    "import os, signal; os.kill(os.getpid(), signal.SIGTERM)",
                ],
                check=False,
            )
            self.assertEqual(result.returncode, 143)
            self.assertEqual(output.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
