from __future__ import annotations

import unittest
from unittest.mock import patch

from rokucli.discovery import (
    SSDP_REQUEST,
    DiscoveredDevice,
    discover_by_http,
    discover_with_fallback,
    fallback_network,
    parse_ssdp_response,
)


class DiscoveryTests(unittest.TestCase):
    def test_request_targets_roku_ecp(self):
        text = SSDP_REQUEST.decode("ascii")
        self.assertIn("M-SEARCH * HTTP/1.1\r\n", text)
        self.assertIn("ST: roku:ecp\r\n", text)
        self.assertNotIn("MX:", text)
        self.assertTrue(text.endswith("\r\n\r\n"))

    def test_headers_are_case_insensitive(self):
        headers = parse_ssdp_response(
            b"HTTP/1.1 200 OK\r\nLocation: http://192.0.2.10:8060/\r\n"
            b"USN: uuid:roku:ecp:123\r\n\r\n"
        )
        self.assertEqual(headers["location"], "http://192.0.2.10:8060/")
        self.assertEqual(headers["usn"], "uuid:roku:ecp:123")

    @patch("rokucli.discovery.local_ipv4", return_value="192.168.1.70")
    def test_default_fallback_uses_local_24(self, _local_ipv4):
        self.assertEqual(str(fallback_network()), "192.168.1.0/24")

    def test_explicit_network_is_normalized(self):
        self.assertEqual(
            str(fallback_network("192.168.1.70/28")),
            "192.168.1.64/28",
        )

    def test_large_network_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "too large"):
            fallback_network("192.168.0.0/16")

    @patch("rokucli.discovery._is_roku")
    def test_http_discovery_returns_only_roku_hosts(self, is_roku):
        is_roku.side_effect = lambda host, _timeout: host == "192.0.2.2"
        devices = discover_by_http(cidr="192.0.2.0/30", max_workers=2)
        self.assertEqual(
            devices,
            [DiscoveredDevice("192.0.2.2", "http://192.0.2.2:8060/")],
        )

    @patch("rokucli.discovery.discover_by_http")
    @patch("rokucli.discovery.discover")
    def test_http_fallback_runs_when_ssdp_is_empty(self, ssdp, http):
        ssdp.return_value = []
        expected = [DiscoveredDevice("192.0.2.2", "http://192.0.2.2:8060/")]
        http.return_value = expected
        self.assertEqual(
            discover_with_fallback(timeout=5, cidr="192.0.2.0/24"),
            expected,
        )
        http.assert_called_once_with(cidr="192.0.2.0/24")

    @patch("rokucli.discovery.discover_by_http")
    @patch("rokucli.discovery.discover")
    def test_http_fallback_is_skipped_when_ssdp_succeeds(self, ssdp, http):
        expected = [DiscoveredDevice("192.0.2.2", "http://192.0.2.2:8060/")]
        ssdp.return_value = expected
        self.assertEqual(discover_with_fallback(), expected)
        http.assert_not_called()


if __name__ == "__main__":
    unittest.main()
