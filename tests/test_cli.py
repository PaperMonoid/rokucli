from __future__ import annotations

from io import StringIO
import unittest
from unittest.mock import Mock, patch

from rokucli.cli import interactive, main, select_device, send_command
from rokucli.client import DeviceInfo, RokuClient, RokuError
from rokucli.discovery import DiscoveredDevice


class CliTests(unittest.TestCase):
    def test_send_netflix_uses_app_launch(self):
        client = Mock(spec=RokuClient)
        send_command(client, "netflix")
        client.launch_netflix.assert_called_once_with()

    def test_send_youtube_uses_app_launch(self):
        client = Mock(spec=RokuClient)
        send_command(client, "youtube")
        client.launch_youtube.assert_called_once_with()

    def test_send_mic_uses_search_key(self):
        client = Mock(spec=RokuClient)
        send_command(client, "mic")
        client.command.assert_called_once_with("mic")

    def test_timed_mic_holds_search_key(self):
        client = Mock(spec=RokuClient)
        send_command(client, "mic", mic_seconds=5)
        client.hold_key.assert_called_once_with("Search", 5)

    def test_interactive_timed_mic(self):
        client = Mock(spec=RokuClient)
        client.host = "192.0.2.10"
        client.device_info.return_value = DeviceInfo("192.0.2.10", "Living Room")
        commands = iter(["mic 5", "quit"])

        with patch("sys.stdout", new=StringIO()):
            interactive(client, input_fn=lambda _prompt: next(commands))

        client.hold_key.assert_called_once_with("Search", 5.0)

    def test_interactive_rejects_invalid_mic_duration(self):
        client = Mock(spec=RokuClient)
        client.host = "192.0.2.10"
        client.device_info.return_value = DeviceInfo("192.0.2.10", "Living Room")
        commands = iter(["mic nope", "mic 0", "quit"])

        with (
            patch("sys.stdout", new=StringIO()),
            patch("sys.stderr", new=StringIO()) as errors,
        ):
            interactive(client, input_fn=lambda _prompt: next(commands))

        self.assertIn("must be a number", errors.getvalue())
        self.assertIn("greater than zero", errors.getvalue())
        client.hold_key.assert_not_called()

    @patch("rokucli.cli.find_devices", return_value=[])
    def test_scan_with_no_devices_is_successful(self, _find):
        with patch("sys.stdout", new=StringIO()) as output:
            result = main(["scan"])
        self.assertEqual(result, 0)
        self.assertIn("No Roku devices found", output.getvalue())

    def test_unknown_command_is_error(self):
        with patch("sys.stderr", new=StringIO()) as output:
            result = main(["dance"])
        self.assertEqual(result, 1)
        self.assertIn("Unknown command", output.getvalue())

    def test_invalid_timeout_is_usage_error(self):
        with patch("sys.stderr", new=StringIO()):
            self.assertEqual(main(["--timeout", "0", "scan"]), 2)

    def test_invalid_mic_seconds_is_usage_error(self):
        with patch("sys.stderr", new=StringIO()):
            self.assertEqual(main(["mic", "--seconds", "0"]), 2)

    def test_seconds_rejected_for_non_mic_command(self):
        with patch("sys.stderr", new=StringIO()) as output:
            self.assertEqual(main(["home", "--seconds", "5"]), 1)
        self.assertIn("only be used with the mic command", output.getvalue())

    @patch("rokucli.cli.resolve_host", return_value="192.0.2.10")
    @patch("rokucli.cli.RokuClient")
    def test_timed_mic_interrupt_exits_cleanly(self, client_type, _resolve):
        client_type.return_value.hold_key.side_effect = KeyboardInterrupt
        with patch("sys.stderr", new=StringIO()) as output:
            result = main(["mic", "--seconds", "5"])
        self.assertEqual(result, 130)
        self.assertIn("Interrupted", output.getvalue())

    @patch("rokucli.cli.save_host")
    def test_selection_rejects_zero(self, _save):
        endpoint = DiscoveredDevice("192.0.2.10", "http://192.0.2.10:8060/")
        client = Mock()
        client.device_info.return_value = DeviceInfo("192.0.2.10", "Living Room")
        with patch("sys.stdout", new=StringIO()):
            with self.assertRaisesRegex(RokuError, "Invalid device selection"):
                select_device(
                    1,
                    input_fn=lambda _prompt: "0",
                    discover_fn=lambda **_kwargs: [endpoint, endpoint],
                    client_factory=lambda *_args, **_kwargs: client,
                )


if __name__ == "__main__":
    unittest.main()
