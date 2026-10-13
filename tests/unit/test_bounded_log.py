#!/usr/bin/env python3
import pathlib
import os
import signal
import subprocess
import sys
import tempfile
import time
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

    def test_rejects_malformed_timeout_arguments(self) -> None:
        for argument, value in (
            ("--timeout-seconds", "0"),
            ("--timeout-seconds", "not-a-number"),
            ("--kill-after-seconds", "-1"),
        ):
            with self.subTest(argument=argument, value=value):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(HELPER),
                        "--output",
                        "unused.log",
                        "--max-bytes",
                        "128",
                        argument,
                        value,
                        "--",
                        sys.executable,
                        "-c",
                        "pass",
                    ],
                    check=False,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 2)

    def test_normal_client_exit_with_collector_timeout_options(self) -> None:
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
                    "--timeout-seconds",
                    "1",
                    "--kill-after-seconds",
                    "0.1",
                    "--",
                    sys.executable,
                    "-c",
                    "print('client completed')",
                ],
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b"client completed\n")

    def test_external_term_returns_signal_status_after_flushing_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "output.log"
            child_ready = pathlib.Path(directory) / "child-ready"
            collector = subprocess.Popen(
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
                    (
                        "import pathlib, sys, time; "
                        "print('before external term', flush=True); "
                        "pathlib.Path(sys.argv[1]).touch(); time.sleep(60)"
                    ),
                    str(child_ready),
                ]
            )
            # Synchronize with both the producer and the collector's SIGTERM
            # handler. A fixed sleep is flaky on loaded runners.
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if collector.poll() is not None:
                    self.fail("collector exited before external SIGTERM test")
                status = pathlib.Path(f"/proc/{collector.pid}/status").read_text()
                caught = next(
                    line.split()[1]
                    for line in status.splitlines()
                    if line.startswith("SigCgt:")
                )
                if child_ready.exists() and (
                    int(caught, 16) & (1 << (signal.SIGTERM - 1))
                ):
                    break
                time.sleep(0.01)
            else:
                collector.kill()
                collector.wait(timeout=5)
                self.fail("collector/producer did not become ready")
            collector.terminate()
            self.assertEqual(collector.wait(timeout=5), 143)
            self.assertEqual(output.read_bytes(), b"before external term\n")

    def test_signal_during_child_spawn_is_forwarded_after_handler_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "output.log"
            runner = (
                "import importlib.util, os, signal, sys\n"
                "source, output = sys.argv[1:]\n"
                "spec = importlib.util.spec_from_file_location('bounded_log', source)\n"
                "module = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(module)\n"
                "original = module.subprocess.Popen\n"
                "def spawn_then_signal(*args, **kwargs):\n"
                "    child = original(*args, **kwargs)\n"
                "    os.kill(os.getpid(), signal.SIGTERM)\n"
                "    return child\n"
                "module.subprocess.Popen = spawn_then_signal\n"
                "sys.argv = [source, '--output', output, '--max-bytes', '128', "
                "'--', sys.executable, '-c', \"import time; time.sleep(60)\"]\n"
                "raise SystemExit(module.main())\n"
            )
            result = subprocess.run(
                [sys.executable, "-c", runner, str(HELPER), str(output)],
                check=False,
                timeout=5,
            )
            self.assertEqual(result.returncode, 143)
            self.assertTrue(output.exists())

    def test_signal_during_atomic_log_write_preserves_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "output.log"
            runner = (
                "import importlib.util, os, signal, sys\n"
                "source, output = sys.argv[1:]\n"
                "spec = importlib.util.spec_from_file_location('bounded_log', source)\n"
                "module = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(module)\n"
                "original = module.write_output\n"
                "def interrupt(*args):\n"
                "    os.kill(os.getpid(), signal.SIGTERM)\n"
                "    original(*args)\n"
                "module.write_output = interrupt\n"
                "sys.argv = [source, '--output', output, '--max-bytes', '128', "
                "'--', sys.executable, '-c', "
                "\"print('late-shutdown', flush=True)\"]\n"
                "raise SystemExit(module.main())\n"
            )
            result = subprocess.run(
                [sys.executable, "-c", runner, str(HELPER), str(output)],
                check=False,
                timeout=5,
            )
            self.assertEqual(result.returncode, 143)
            self.assertEqual(output.read_bytes(), b"late-shutdown\n")

    def test_timeout_kills_term_ignoring_process_group_and_flushes_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "output.log"
            pid_file = pathlib.Path(directory) / "pids"
            result = subprocess.run(
                [
                    sys.executable,
                    str(HELPER),
                    "--output",
                    str(output),
                    "--max-bytes",
                    "128",
                    "--timeout-seconds",
                    "0.2",
                    "--kill-after-seconds",
                    "0.1",
                    "--",
                    sys.executable,
                    "-c",
                    (
                        "import os, pathlib, signal, sys, time; "
                        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                        "child = os.fork(); "
                        "child and pathlib.Path(sys.argv[1]).write_text("
                        "f'{os.getpid()} {child}', encoding='utf-8'); "
                        "print('initial diagnostic', flush=True); "
                        "time.sleep(60)"
                    ),
                    str(pid_file),
                ],
                check=False,
                timeout=5,
            )
            self.assertEqual(result.returncode, 124)
            self.assertIn(b"initial diagnostic\n", output.read_bytes())

            deadline = time.monotonic() + 1
            pids = [int(pid) for pid in pid_file.read_text(encoding="utf-8").split()]
            while time.monotonic() < deadline:
                remaining = []
                for pid in pids:
                    try:
                        os.kill(pid, 0)
                        # Containers without a subreaper may leave a terminated
                        # grandchild as a zombie. A zombie cannot execute or
                        # retain the stdout pipe, so it is not a live escape.
                        stat = pathlib.Path(f"/proc/{pid}/stat").read_text()
                    except (ProcessLookupError, FileNotFoundError):
                        continue
                    if stat.rsplit(") ", 1)[1].split()[0] == "Z":
                        continue
                    remaining.append(pid)
                if not remaining:
                    break
                time.sleep(0.02)
            else:
                self.fail("TERM-ignoring collector child escaped its process group")

    def test_timeout_kills_descendant_even_if_it_closed_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "output.log"
            pid_file = pathlib.Path(directory) / "grandchild.pid"
            program = (
                "import os, pathlib, signal, sys, time\n"
                "pid = os.fork()\n"
                "if pid == 0:\n"
                "    os.close(1)\n"
                "    os.close(2)\n"
                "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "    time.sleep(60)\n"
                "    os._exit(0)\n"
                "pathlib.Path(sys.argv[1]).write_text(str(pid))\n"
                "print('parent diagnostic', flush=True)\n"
                "time.sleep(60)\n"
            )
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(HELPER),
                        "--output", str(output),
                        "--max-bytes", "128",
                        "--timeout-seconds", "0.5",
                        "--kill-after-seconds", "0.1",
                        "--",
                        sys.executable, "-c", program, str(pid_file),
                    ],
                    check=False,
                    timeout=6,
                )
                self.assertEqual(result.returncode, 124)
                self.assertIn(b"parent diagnostic\n", output.read_bytes())
                pid = int(pid_file.read_text(encoding="utf-8"))
                deadline = time.monotonic() + 1
                while time.monotonic() < deadline:
                    try:
                        proc_stat = pathlib.Path(f"/proc/{pid}/stat").read_text()
                    except FileNotFoundError:
                        break
                    if proc_stat.rsplit(") ", 1)[1].split()[0] == "Z":
                        break
                    time.sleep(0.02)
                else:
                    self.fail("TERM-ignoring grandchild remained alive after EOF")
            finally:
                if pid_file.exists():
                    pid = int(pid_file.read_text(encoding="utf-8"))
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    unittest.main()
