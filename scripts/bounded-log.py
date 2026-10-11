#!/usr/bin/env python3
"""Run a command while retaining bounded first and last output diagnostics."""

from __future__ import annotations

import argparse
import collections
import math
import os
import pathlib
import selectors
import signal
import subprocess
import sys
import tempfile
import time


EXTERNAL_SIGNAL_GRACE_SECONDS = 10.0
REAP_GRACE_SECONDS = 1.0
SELECT_INTERVAL_SECONDS = 0.1


def positive_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive number") from error
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("must be a positive number")
    return seconds


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture command output without allowing an unbounded log file."
    )
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--max-bytes", required=True, type=int)
    parser.add_argument("--timeout-seconds", type=positive_seconds)
    parser.add_argument("--kill-after-seconds", type=positive_seconds)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()

    if arguments.max_bytes <= 0:
        parser.error("--max-bytes must be positive")
    if arguments.kill_after_seconds is not None and arguments.timeout_seconds is None:
        parser.error("--kill-after-seconds requires --timeout-seconds")
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


def write_output(
    output: pathlib.Path,
    retained: bytearray,
    head: bytearray,
    tail: collections.deque[bytes],
    truncated: bool,
    marker: bytes,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, delete=False) as temporary:
        if truncated:
            temporary.write(head)
            temporary.write(marker)
            temporary.write(b"".join(tail))
        else:
            temporary.write(retained)
        temporary_name = temporary.name
    os.replace(temporary_name, output)


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

    child: subprocess.Popen[bytes] | None = None
    externally_signalled: int | None = None
    termination_started_at: float | None = None
    kill_sent = False
    reap_deadline: float | None = None
    stream_open = True
    deadline = (
        time.monotonic() + arguments.timeout_seconds
        if arguments.timeout_seconds is not None
        else None
    )
    timed_out = False
    prior_handlers: dict[int, signal.Handlers] = {}

    def send_group_signal(signum: int) -> None:
        if child is None:
            return
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass

    def forward_signal(signum: int, _frame: object) -> None:
        nonlocal externally_signalled
        if externally_signalled is None:
            externally_signalled = signum
            send_group_signal(signum)

    def begin_termination(now: float) -> None:
        nonlocal termination_started_at
        if termination_started_at is None:
            termination_started_at = now
            send_group_signal(signal.SIGTERM)

    def close_stream() -> None:
        nonlocal stream_open
        if stream_open:
            selector.unregister(stream)
            stream.close()
            stream_open = False

    for signum in (signal.SIGTERM, signal.SIGINT):
        prior_handlers[signum] = signal.signal(signum, forward_signal)

    # Install forwarding before starting the detached child session. A signal
    # received during Popen otherwise kills this collector before it can stop
    # a Docker CLI that is still creating its container.
    child = subprocess.Popen(
        arguments.command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    assert child.stdout is not None
    stream = child.stdout
    os.set_blocking(stream.fileno(), False)
    selector = selectors.DefaultSelector()
    selector.register(stream, selectors.EVENT_READ)

    try:
        while True:
            now = time.monotonic()
            status = child.poll()

            if externally_signalled is not None:
                begin_termination(now)
            if deadline is not None and status is None and now >= deadline:
                timed_out = True
                begin_termination(now)

            if status is not None and termination_started_at is None:
                # A command can leave same-session descendants holding stdout open.
                # Stop them too, instead of allowing a descendant to outlive the log.
                try:
                    os.killpg(child.pid, 0)
                except ProcessLookupError:
                    pass
                else:
                    begin_termination(now)

            if (
                termination_started_at is not None
                and not kill_sent
                and now
                >= termination_started_at
                + (
                    arguments.kill_after_seconds
                    if arguments.kill_after_seconds is not None
                    else EXTERNAL_SIGNAL_GRACE_SECONDS
                )
            ):
                send_group_signal(signal.SIGKILL)
                kill_sent = True
                reap_deadline = now + REAP_GRACE_SECONDS

            if status is not None and not stream_open:
                # EOF does not prove that same-process-group descendants have
                # stopped: they may close stdout and ignore SIGTERM. Keep the
                # TERM/KILL deadline active until the group exits or the
                # bounded post-SIGKILL reap grace expires.
                try:
                    os.killpg(child.pid, 0)
                except ProcessLookupError:
                    break
                if termination_started_at is None:
                    begin_termination(now)
            if reap_deadline is not None and now >= reap_deadline:
                # SIGKILL should make this path unreachable, but do not let an
                # uninterruptible child or inherited descriptor block log flushing.
                close_stream()
                break

            wait_seconds = SELECT_INTERVAL_SECONDS
            upcoming = [candidate for candidate in (deadline, reap_deadline) if candidate]
            if termination_started_at is not None and not kill_sent:
                upcoming.append(
                    termination_started_at
                    + (
                        arguments.kill_after_seconds
                        if arguments.kill_after_seconds is not None
                        else EXTERNAL_SIGNAL_GRACE_SECONDS
                    )
                )
            if upcoming:
                wait_seconds = min(wait_seconds, max(0.0, min(upcoming) - now))

            if stream_open:
                for _key, _events in selector.select(wait_seconds):
                    try:
                        chunk = os.read(stream.fileno(), 64 * 1024)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        close_stream()
                        continue
                    if not truncated:
                        retained.extend(chunk)
                        if len(retained) > arguments.max_bytes:
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
            else:
                time.sleep(wait_seconds)
    finally:
        selector.close()
        try:
            # Retain signal forwarding until the atomic replacement completes;
            # restoring SIGTERM/SIGINT first could discard timeout diagnostics.
            write_output(arguments.output, retained, head, tail, truncated, marker)
        finally:
            for signum, handler in prior_handlers.items():
                signal.signal(signum, handler)

    # poll() has reaped the direct child when it exited. If it did not exit after
    # SIGKILL, keep the collector bounded and still preserve its diagnostics.
    status = child.poll()
    if externally_signalled is not None:
        return 128 + externally_signalled
    if timed_out:
        return 124
    if status is None:
        return 124
    return 128 + -status if status < 0 else status


if __name__ == "__main__":
    raise SystemExit(main())
