"""Bounded persistent workers for the upstream JavaScript protocol decoder."""

from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import threading
import uuid
from contextlib import suppress
from pathlib import Path


class _NodeDecryptWorker:
    def __init__(self, source_path: Path, timeout: float) -> None:
        self._source_path = source_path
        self._timeout = timeout
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._responses: queue.Queue[str | None] = queue.Queue()
        self._reader: threading.Thread | None = None

    def decrypt(self, data: str) -> str:
        with self._lock:
            process = self._ensure_process()
            request_id = uuid.uuid4().hex
            assert process.stdin is not None
            assert process.stdout is not None
            try:
                process.stdin.write(
                    json.dumps({"id": request_id, "data": data}, ensure_ascii=False) + "\n"
                )
                process.stdin.flush()
                try:
                    line = self._responses.get(timeout=self._timeout)
                except queue.Empty as exc:
                    raise TimeoutError("protocol decrypt worker timed out") from exc
                if not line:
                    raise RuntimeError("protocol decrypt worker stopped unexpectedly")
                response = json.loads(line)
                if response.get("id") != request_id:
                    raise RuntimeError("protocol decrypt worker response mismatch")
                if response.get("error"):
                    raise RuntimeError(str(response["error"]))
                return str(response.get("result") or "")
            except Exception:
                self._stop_locked()
                raise

    def close(self) -> None:
        with self._lock:
            self._stop_locked()

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        worker_path = Path(__file__).with_name("protocol_decrypt_worker.cjs")
        self._responses = queue.Queue()
        self._process = subprocess.Popen(
            ["node", str(worker_path), str(self._source_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env={**os.environ, "NODE_NO_WARNINGS": "1"},
        )
        self._reader = threading.Thread(
            target=self._read_responses,
            args=(self._process, self._responses),
            name="xianyu-protocol-reader",
            daemon=True,
        )
        self._reader.start()
        return self._process

    @staticmethod
    def _read_responses(
        process: subprocess.Popen[str],
        responses: queue.Queue[str | None],
    ) -> None:
        stream = process.stdout
        if stream is None:
            responses.put(None)
            return
        try:
            for line in stream:
                responses.put(line)
        finally:
            responses.put(None)

    def _stop_locked(self) -> None:
        process = self._process
        reader = self._reader
        self._process = None
        self._reader = None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                with suppress(OSError):
                    stream.close()
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=1)


class ProtocolDecryptPool:
    def __init__(self, source_path: Path, *, size: int = 2, timeout: float = 8.0) -> None:
        self._workers = tuple(
            _NodeDecryptWorker(source_path, timeout) for _ in range(max(1, size))
        )
        self._available: queue.Queue[_NodeDecryptWorker] = queue.Queue()
        for worker in self._workers:
            self._available.put(worker)

    def decrypt(self, data: str) -> str:
        worker = self._available.get()
        try:
            return worker.decrypt(data)
        finally:
            self._available.put(worker)

    def close(self) -> None:
        for worker in self._workers:
            worker.close()


_pools: dict[Path, ProtocolDecryptPool] = {}
_pools_lock = threading.Lock()


def get_protocol_decryptor(source_path: Path):  # type: ignore[no-untyped-def]
    resolved = source_path.resolve()
    with _pools_lock:
        pool = _pools.get(resolved)
        if pool is None:
            pool = ProtocolDecryptPool(resolved, size=4)
            _pools[resolved] = pool
    return pool.decrypt


def shutdown_protocol_workers() -> None:
    with _pools_lock:
        pools = tuple(_pools.values())
        _pools.clear()
    for pool in pools:
        pool.close()


atexit.register(shutdown_protocol_workers)
