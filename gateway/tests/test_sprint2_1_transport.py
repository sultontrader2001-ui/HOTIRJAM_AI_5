"""Sprint 2.1 transport foundation tests — no AI, no NT."""

from __future__ import annotations

import json
import socket
import threading
import time

from hotirjam_gateway.transport import (
    MessageReceiver,
    TransportServer,
    TransportSession,
)


class RecordingValidation:
    """Test double for the validation layer."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, object]] = []
        self.event = threading.Event()

    def on_raw_message(
        self,
        raw: str,
        data: object,
        session: TransportSession,
    ) -> None:
        self.messages.append((raw, data))
        self.event.set()


def _wait_until(predicate, timeout: float = 2.0, interval: float = 0.01) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("condition not met before timeout")


def test_server_startup() -> None:
    server = TransportServer(host="127.0.0.1", port=0)
    host, port = server.start()
    try:
        assert server.wait_ready(1.0)
        assert server.is_running
        assert host == "127.0.0.1"
        assert port > 0
        assert server.port == port
    finally:
        server.stop()
    assert server.is_running is False


def test_client_connect_and_disconnect() -> None:
    server = TransportServer(host="127.0.0.1", port=0)
    host, port = server.start()
    try:
        sock = socket.create_connection((host, port), timeout=2.0)
        _wait_until(lambda: server.active_session is not None)
        session = server.active_session
        assert session is not None
        assert session.connection_id
        assert session.connected_at > 0
        assert session.messages_received == 0

        sock.close()
        _wait_until(lambda: server.active_session is None)
    finally:
        server.stop()


def test_raw_message_receive() -> None:
    validation = RecordingValidation()
    server = TransportServer(host="127.0.0.1", port=0, validation=validation)
    host, port = server.start()
    try:
        sock = socket.create_connection((host, port), timeout=2.0)
        payload = {"hello": "world", "n": 1}
        line = (json.dumps(payload) + "\n").encode("utf-8")
        sock.sendall(line)

        assert validation.event.wait(2.0)
        assert len(validation.messages) == 1
        raw, data = validation.messages[0]
        assert json.loads(raw) == payload
        assert data == payload

        _wait_until(
            lambda: server.active_session is not None
            and server.active_session.messages_received == 1
        )
        session = server.active_session
        assert session is not None
        # Framing newline is not counted; payload bytes are.
        assert session.bytes_received == len(line) - 1
        assert session.last_message_time is not None
        sock.close()
    finally:
        server.stop()


def test_invalid_json_not_forwarded() -> None:
    validation = RecordingValidation()
    invalids: list[str] = []

    session = TransportSession()
    receiver = MessageReceiver(
        session,
        validation=validation,
        on_invalid=lambda raw, _s: invalids.append(raw),
    )
    receiver.feed(b"not-json\n")
    assert validation.messages == []
    assert invalids == ["not-json"]
    assert session.messages_received == 1

    server = TransportServer(host="127.0.0.1", port=0, validation=validation)
    host, port = server.start()
    try:
        sock = socket.create_connection((host, port), timeout=2.0)
        sock.sendall(b"{broken\n")
        _wait_until(
            lambda: server.active_session is not None
            and server.active_session.messages_received >= 1
        )
        time.sleep(0.05)
        assert validation.messages == []
        sock.close()
    finally:
        server.stop()


def test_clean_shutdown_with_active_client() -> None:
    server = TransportServer(host="127.0.0.1", port=0)
    host, port = server.start()
    sock = socket.create_connection((host, port), timeout=2.0)
    try:
        _wait_until(lambda: server.active_session is not None)
        server.stop()
        assert server.is_running is False
        assert server.active_session is None
        # Client should eventually see EOF / closed peer.
        sock.settimeout(1.0)
        data = sock.recv(16)
        assert data == b""
    finally:
        try:
            sock.close()
        except OSError:
            pass


def test_one_active_connection_refuses_second() -> None:
    server = TransportServer(host="127.0.0.1", port=0)
    host, port = server.start()
    try:
        first = socket.create_connection((host, port), timeout=2.0)
        _wait_until(lambda: server.active_session is not None)
        first_id = server.active_session.connection_id  # type: ignore[union-attr]

        second = socket.create_connection((host, port), timeout=2.0)
        second.settimeout(1.0)
        # Second peer is closed by server (refuse).
        closed = second.recv(16)
        assert closed == b""
        second.close()

        assert server.active_session is not None
        assert server.active_session.connection_id == first_id
        first.close()
        _wait_until(lambda: server.active_session is None)
    finally:
        server.stop()


def test_package_transport_has_no_ai_imports() -> None:
    import ast
    from pathlib import Path

    import hotirjam_gateway.transport as t
    import hotirjam_gateway.transport.receiver as r
    import hotirjam_gateway.transport.server as s
    import hotirjam_gateway.transport.session as sess

    banned_roots = ("hotirjam_ai5", "ninjatrader", "NinjaTrader")
    for mod in (t, r, s, sess):
        path = Path(mod.__file__ or "")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                lowered = name.lower()
                assert not any(b.lower() in lowered for b in banned_roots), name
