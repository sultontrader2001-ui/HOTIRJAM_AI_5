"""TCP transport server — accept one client; read UTF-8 JSON lines."""

from __future__ import annotations

import socket
import threading
import time
from typing import Any

from hotirjam_gateway.logging import get_logger
from hotirjam_gateway.transport.receiver import MessageReceiver, ValidationLayer
from hotirjam_gateway.transport.session import TransportSession

_log = get_logger(__name__)

_DEFAULT_HOST = "127.0.0.1"
_RECV_SIZE = 65536
_ACCEPT_POLL_S = 0.2
_JOIN_TIMEOUT_S = 5.0


class TransportServer:
    """Listen for TCP clients; serve at most one active connection.

    Framing: newline-delimited UTF-8 JSON (NDJSON). No Tick/DOM/AI knowledge.
    """

    def __init__(
        self,
        host: str = _DEFAULT_HOST,
        port: int = 0,
        *,
        validation: ValidationLayer | None = None,
        backlog: int = 5,
    ) -> None:
        self._host = host
        self._port = int(port)
        self._validation = validation
        self._backlog = backlog

        self._sock: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._client_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._lock = threading.Lock()

        self._active_session: TransportSession | None = None
        self._bound_port: int | None = None
        self._started = False
        self._error: BaseException | None = None

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        """Bound listen port (available after ``start``)."""
        if self._bound_port is not None:
            return self._bound_port
        return self._port

    @property
    def is_running(self) -> bool:
        return self._started and not self._stop.is_set()

    @property
    def active_session(self) -> TransportSession | None:
        with self._lock:
            return self._active_session

    def start(self) -> tuple[str, int]:
        """Bind, listen, and start the accept loop. Returns ``(host, port)``."""
        if self._started:
            raise RuntimeError("TransportServer already started")

        self._stop.clear()
        self._ready.clear()
        self._error = None

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self._host, self._port))
        sock.listen(self._backlog)
        sock.settimeout(_ACCEPT_POLL_S)
        self._sock = sock
        self._bound_port = int(sock.getsockname()[1])
        self._started = True

        self._accept_thread = threading.Thread(
            target=self._accept_loop,
            name="gateway-transport-accept",
            daemon=True,
        )
        self._accept_thread.start()
        self._ready.set()

        _log.info(
            "Gateway Started",
            extra={
                "gateway_event": "Gateway Started",
                "host": self._host,
                "port": self._bound_port,
            },
        )
        return self._host, self._bound_port

    def wait_ready(self, timeout: float = 2.0) -> bool:
        return self._ready.wait(timeout)

    def stop(self, *, timeout: float = _JOIN_TIMEOUT_S) -> None:
        """Stop accepting and close any active client (clean shutdown)."""
        if not self._started:
            return
        self._stop.set()

        sock = self._sock
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

        if self._accept_thread is not None:
            self._accept_thread.join(timeout=timeout)
            self._accept_thread = None

        if self._client_thread is not None:
            self._client_thread.join(timeout=timeout)
            self._client_thread = None

        with self._lock:
            self._active_session = None

        self._sock = None
        self._started = False
        self._bound_port = None

    def __enter__(self) -> TransportServer:
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                client, addr = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                if self._stop.is_set():
                    break
                continue

            with self._lock:
                busy = self._active_session is not None

            if busy:
                # One active connection only — refuse extras.
                try:
                    client.close()
                except OSError:
                    pass
                continue

            session = TransportSession(
                connected_at=time.time(),
                remote_addr=f"{addr[0]}:{addr[1]}",
            )
            with self._lock:
                self._active_session = session

            _log.info(
                "Client Connected",
                extra={
                    "gateway_event": "Client Connected",
                    "connection_id": session.connection_id,
                    "remote_addr": session.remote_addr,
                },
            )

            self._client_thread = threading.Thread(
                target=self._client_loop,
                args=(client, session),
                name="gateway-transport-client",
                daemon=True,
            )
            self._client_thread.start()

    def _client_loop(self, client: socket.socket, session: TransportSession) -> None:
        receiver = MessageReceiver(session, validation=self._validation)
        client.settimeout(_ACCEPT_POLL_S)
        try:
            while not self._stop.is_set():
                try:
                    chunk = client.recv(_RECV_SIZE)
                except TimeoutError:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                receiver.feed(chunk)
        finally:
            try:
                client.close()
            except OSError:
                pass
            receiver.flush_incomplete()
            with self._lock:
                if self._active_session is session:
                    self._active_session = None
            _log.info(
                "Client Disconnected",
                extra={
                    "gateway_event": "Client Disconnected",
                    "connection_id": session.connection_id,
                    "messages_received": session.messages_received,
                    "bytes_received": session.bytes_received,
                },
            )
