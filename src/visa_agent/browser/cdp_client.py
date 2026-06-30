from __future__ import annotations

import base64
import hashlib
import json
import os
from socket import create_connection
import ssl
import struct
from types import TracebackType
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen


def list_debug_targets(port: int = 9222) -> list[dict[str, Any]]:
    with urlopen(f"http://127.0.0.1:{port}/json/list") as response:
        return json.loads(response.read().decode())


def find_target_websocket_url(url_substring: str, port: int = 9222) -> str:
    targets = list_debug_targets(port=port)
    for target in targets:
        if url_substring in (target.get("url") or ""):
            ws_url = target.get("webSocketDebuggerUrl")
            if ws_url:
                return str(ws_url)
    raise RuntimeError(f"No target found containing {url_substring!r} on port {port}")


class CDPWebSocket:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self._socket = None
        self._message_id = 0

    def __enter__(self) -> "CDPWebSocket":
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def connect(self) -> None:
        parsed = urlparse(self.ws_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        sock = create_connection((host, port), timeout=10)
        if parsed.scheme == "wss":
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=host)

        key = base64.b64encode(os.urandom(16)).decode()
        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).encode()
        sock.sendall(handshake)
        response = self._read_http_headers(sock)
        if "101" not in response.splitlines()[0]:
            raise RuntimeError(f"WebSocket handshake failed: {response!r}")
        accept = self._header_value(response, "Sec-WebSocket-Accept")
        expected = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()
        if accept != expected:
            raise RuntimeError("WebSocket accept key mismatch")
        self._socket = sock

    def close(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._message_id += 1
        message_id = self._message_id
        payload = {"id": message_id, "method": method, "params": params or {}}
        self._send_json(payload)
        while True:
            message = self._recv_json()
            if message.get("id") == message_id:
                return message

    def _send_json(self, payload: dict[str, Any]) -> None:
        assert self._socket is not None
        data = json.dumps(payload).encode()
        frame = bytearray()
        frame.append(0x81)
        mask_bit = 0x80
        length = len(data)
        if length < 126:
            frame.append(mask_bit | length)
        elif length < (1 << 16):
            frame.append(mask_bit | 126)
            frame.extend(struct.pack("!H", length))
        else:
            frame.append(mask_bit | 127)
            frame.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        frame.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        frame.extend(masked)
        self._socket.sendall(frame)

    def _recv_json(self) -> dict[str, Any]:
        assert self._socket is not None
        first = self._read_exact(2)
        payload_len = first[1] & 0x7F
        if payload_len == 126:
            payload_len = struct.unpack("!H", self._read_exact(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack("!Q", self._read_exact(8))[0]
        masked = bool(first[1] & 0x80)
        mask = self._read_exact(4) if masked else b""
        payload = self._read_exact(payload_len)
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        opcode = first[0] & 0x0F
        if opcode == 0x8:
            raise RuntimeError("WebSocket closed by remote endpoint")
        if opcode != 0x1:
            return {}
        return json.loads(payload.decode())

    def _read_exact(self, size: int) -> bytes:
        assert self._socket is not None
        chunks = []
        remaining = size
        while remaining:
            chunk = self._socket.recv(remaining)
            if not chunk:
                raise RuntimeError("Unexpected EOF while reading WebSocket frame")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    @staticmethod
    def _read_http_headers(sock) -> str:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data.decode(errors="replace")

    @staticmethod
    def _header_value(response: str, name: str) -> str | None:
        prefix = name.lower() + ":"
        for line in response.splitlines():
            if line.lower().startswith(prefix):
                return line.split(":", 1)[1].strip()
        return None

