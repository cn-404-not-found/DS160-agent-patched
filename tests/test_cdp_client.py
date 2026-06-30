from __future__ import annotations

import unittest

from visa_agent.browser.cdp_client import CDPWebSocket


class CDPClientTests(unittest.TestCase):
    def test_accept_header_name_lookup_is_case_insensitive(self) -> None:
        response = "HTTP/1.1 101 Switching Protocols\r\nSec-WebSocket-Accept: abc\r\n\r\n"
        self.assertEqual(CDPWebSocket._header_value(response, "sec-websocket-accept"), "abc")


if __name__ == "__main__":
    unittest.main()

