from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional


logger = logging.getLogger(__name__)


class _PipeSocket:
    """Lightweight wrapper to mimic socket API on top of an OS pipe fd."""

    def __init__(self, fd: int) -> None:
        self._fd = fd

    def fileno(self) -> int:  # pragma: no cover - thin wrapper
        return self._fd

    def setblocking(self, flag: bool) -> None:
        os.set_blocking(self._fd, flag)

    def close(self) -> None:
        try:
            os.close(self._fd)
        except OSError:
            pass

    def send(self, data: bytes) -> int:
        return os.write(self._fd, data)

    def recv(self, n: int) -> bytes:
        return os.read(self._fd, n)


class PipeSelectorEventLoop(asyncio.SelectorEventLoop):
    """Selector event loop that uses an OS pipe for cross-thread wakeups.

    The default asyncio loop uses a Unix socketpair; in our environment
    cross-thread writes to AF_UNIX sockets are blocked (EPERM), so
    call_soon_threadsafe never wakes the loop. A pipe works fine, so we
    swap the self-pipe implementation to use os.pipe().
    """

    _ssock: Optional[_PipeSocket]
    _csock: Optional[_PipeSocket]

    def _make_self_pipe(self) -> None:
        r_fd, w_fd = os.pipe()
        os.set_blocking(r_fd, False)
        os.set_blocking(w_fd, False)
        self._ssock = _PipeSocket(r_fd)
        self._csock = _PipeSocket(w_fd)
        self._internal_fds += 1
        self._add_reader(self._ssock.fileno(), self._read_from_self)

    def _close_self_pipe(self) -> None:
        if self._ssock is None or self._csock is None:
            return
        self._remove_reader(self._ssock.fileno())
        self._ssock.close()
        self._csock.close()
        self._ssock = None
        self._csock = None
        self._internal_fds -= 1

    def _read_from_self(self) -> None:
        while True:
            try:
                data = self._ssock.recv(4096)  # type: ignore[union-attr]
                if not data:
                    break
                self._process_self_data(data)
            except InterruptedError:
                continue
            except BlockingIOError:
                break

    def _write_to_self(self) -> None:
        csock = self._csock
        if csock is None:
            return
        try:
            csock.send(b"\0")
        except BlockingIOError:
            return
        except OSError:
            if self._debug:
                logger.debug(
                    "Failed to write wakeup byte into the pipe-based self pipe",
                    exc_info=True,
                )


class PipeEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loop policy that installs PipeSelectorEventLoop."""

    def new_event_loop(self) -> asyncio.AbstractEventLoop:
        return PipeSelectorEventLoop()
