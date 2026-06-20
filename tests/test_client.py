from __future__ import annotations

from io import BytesIO
import unittest
from unittest.mock import patch
from urllib.error import URLError

from rokucli.client import (
    KEYS,
    RokuClient,
    RokuConnectionError,
    RokuError,
    normalize_host,
)


class FakeResponse:
    def __init__(self, body: bytes = b""):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class ClientTests(unittest.TestCase):
    @patch("rokucli.client.urlopen")
    def test_all_remote_commands_post_expected_key(self, urlopen):
        urlopen.return_value = FakeResponse()
        client = RokuClient("192.0.2.10")

        for command, key in KEYS.items():
            with self.subTest(command=command):
                client.command(command)
                request = urlopen.call_args.args[0]
                self.assertEqual(request.full_url, f"http://192.0.2.10:8060/keypress/{key}")
                self.assertEqual(request.get_method(), "POST")

    @patch("rokucli.client.urlopen")
    def test_aliases(self, urlopen):
        urlopen.return_value = FakeResponse()
        client = RokuClient("192.0.2.10")
        client.command("pause")
        client.command("next")

        self.assertTrue(urlopen.call_args_list[0].args[0].full_url.endswith("/keypress/Play"))
        self.assertTrue(urlopen.call_args_list[1].args[0].full_url.endswith("/keypress/Fwd"))

    def test_ir_volume_commands_are_not_exposed(self):
        client = RokuClient("192.0.2.10")
        for command in ("volume-up", "volume-down", "mute", "volup", "vol-"):
            with self.subTest(command=command):
                with self.assertRaisesRegex(RokuError, "Unknown command"):
                    client.command(command)

    @patch("rokucli.client.urlopen")
    def test_power_on_posts_power_on_key(self, urlopen):
        urlopen.return_value = FakeResponse()

        RokuClient("192.0.2.10").command("power-on")

        request = urlopen.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/keypress/PowerOn"))
        self.assertEqual(request.get_method(), "POST")

    @patch("rokucli.client.time.sleep")
    @patch("rokucli.client.urlopen")
    def test_hold_key_sends_down_waits_and_sends_up(self, urlopen, sleep):
        urlopen.return_value = FakeResponse()

        RokuClient("192.0.2.10").hold_key("Search", 5)

        self.assertTrue(
            urlopen.call_args_list[0].args[0].full_url.endswith("/keydown/Search")
        )
        sleep.assert_called_once_with(5)
        self.assertTrue(
            urlopen.call_args_list[1].args[0].full_url.endswith("/keyup/Search")
        )

    @patch("rokucli.client.time.sleep", side_effect=KeyboardInterrupt)
    @patch("rokucli.client.urlopen")
    def test_hold_key_releases_after_interrupt(self, urlopen, _sleep):
        urlopen.return_value = FakeResponse()

        with self.assertRaises(KeyboardInterrupt):
            RokuClient("192.0.2.10").hold_key("Search", 5)

        self.assertTrue(
            urlopen.call_args_list[-1].args[0].full_url.endswith("/keyup/Search")
        )

    @patch("rokucli.client.urlopen")
    def test_device_info_uses_user_name(self, urlopen):
        urlopen.return_value = FakeResponse(
            b"""<device-info>
                <user-device-name>Living Room</user-device-name>
                <model-name>Roku TV</model-name>
                <serial-number>ABC123</serial-number>
            </device-info>"""
        )
        info = RokuClient("192.0.2.10").device_info()
        self.assertEqual(info.name, "Living Room")
        self.assertEqual(info.model, "Roku TV")
        self.assertEqual(info.serial_number, "ABC123")

    @patch("rokucli.client.urlopen")
    def test_netflix_is_looked_up_and_launched(self, urlopen):
        urlopen.side_effect = [
            FakeResponse(
                b'<apps><app id="12">Other</app><app id="99">Netflix</app></apps>'
            ),
            FakeResponse(),
        ]

        RokuClient("192.0.2.10").launch_netflix()

        launch = urlopen.call_args_list[1].args[0]
        self.assertEqual(launch.full_url, "http://192.0.2.10:8060/launch/99")
        self.assertEqual(launch.get_method(), "POST")

    @patch("rokucli.client.urlopen")
    def test_missing_netflix_is_clear(self, urlopen):
        urlopen.return_value = FakeResponse(b'<apps><app id="12">Other</app></apps>')
        with self.assertRaisesRegex(RokuError, "not installed"):
            RokuClient("192.0.2.10").launch_netflix()

    @patch("rokucli.client.urlopen")
    def test_youtube_is_looked_up_and_launched(self, urlopen):
        urlopen.side_effect = [
            FakeResponse(
                b'<apps><app id="12">Other</app><app id="55">YouTube</app></apps>'
            ),
            FakeResponse(),
        ]

        RokuClient("192.0.2.10").launch_youtube()

        launch = urlopen.call_args_list[1].args[0]
        self.assertEqual(launch.full_url, "http://192.0.2.10:8060/launch/55")
        self.assertEqual(launch.get_method(), "POST")

    @patch("rokucli.client.urlopen", side_effect=URLError("timed out"))
    def test_connection_failure_is_wrapped(self, _urlopen):
        with self.assertRaisesRegex(RokuConnectionError, "Could not reach"):
            RokuClient("192.0.2.10").device_info()

    def test_normalize_host_accepts_urls_and_ports(self):
        self.assertEqual(normalize_host("http://192.0.2.10:8060/path"), "192.0.2.10")
        self.assertEqual(normalize_host("roku.local:8060"), "roku.local")


if __name__ == "__main__":
    unittest.main()
