#!/usr/bin/env python3
"""Run a command while retaining bounded first and last output diagnostics."""

from __future__ import annotations

import argparse
import collections
import os
import pathlib
import signal
import subprocess
import sys
import tempfile


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture command output without allowing an unbounded log file."
    )
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--max-bytes", required=True, type=int)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()

    if arguments.max_bytes <= 0:
        parser.error("--max-bytes must be positive")
    if not arguments.command or arguments.command[0] != "--":
        parser.error("command must follow --")
    if len(arguments.command) == 1:
        parser.error("command must not be empty")
    arguments.command = arguments.command[1:]
    return arguments


def retain_tail(chunks: collections.deque[bytes], size: int, limit: int) -> int:
    while size > limit and chunks:
        excess = size - limit
        first = chunks[0]
        if len(first) <= excess:
            size -= len(first)
            chunks.popleft()
        else:
            chunks[0] = first[excess:]
            size -= excess
    return size


def main() -> int:
    arguments = parse_arguments()
    marker = b"\n\n[output truncated; retaining first and last diagnostics]\n\n"
    if arguments.max_bytes <= len(marker):
        raise SystemExit("--max-bytes must exceed the truncation marker size")

    head_limit = (arguments.max_bytes - len(marker)) // 2
    tail_limit = arguments.max_bytes - len(marker) - head_limit
    retained = bytearray()
    head = bytearray()
    tail: collections.deque[bytes] = collections.deque()
    tail_size = 0
    truncated = False

    child = subprocess.Popen(
        arguments.command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    def forward_signal(signum: int, _frame: object) -> None:
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass

    signal.signal(signal.SIGTERM, forward_signal)
    signal.signal(signal.SIGINT, forward_signal)

    assert child.stdout is not None
    while chunk := child.stdout.read(64 * 1024):
        if not truncated:
            retained.extend(chunk)
            if len(retained) <= arguments.max_bytes:
                continue

            truncated = True
            head.extend(retained[:head_limit])
            tail.append(bytes(retained[head_limit:]))
            tail_size = len(tail[0])
            tail_size = retain_tail(tail, tail_size, tail_limit)
            retained.clear()
        else:
            tail.append(chunk)
            tail_size += len(chunk)
            tail_size = retain_tail(tail, tail_size, tail_limit)

    status = child.wait()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=arguments.output.parent, delete=False
    ) as temporary:
        if truncated:
            temporary.write(head)
            temporary.write(marker)
            temporary.write(b"".join(tail))
        else:
            temporary.write(retained)
        temporary_name = temporary.name
    os.replace(temporary_name, arguments.output)
    return 128 + -status if status < 0 else status


if __name__ == "__main__":
    raise SystemExit(main())
