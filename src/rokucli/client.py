"""Minimal Roku External Control Protocol client."""

from __future__ import annotations

from dataclasses import dataclass
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


class RokuError(Exception):
    """Base error shown to CLI users."""


class RokuConnectionError(RokuError):
    """The Roku could not be reached."""


class RokuResponseError(RokuError):
    """The Roku returned invalid or unsuccessful data."""


@dataclass(frozen=True)
class DeviceInfo:
    host: str
    name: str
    model: str = ""
    serial_number: str = ""


KEYS = {
    "home": "Home",
    "back": "Back",
    "power-on": "PowerOn",
    "power-off": "PowerOff",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "ok": "Select",
    "play-pause": "Play",
    "rewind": "Rev",
    "fast-forward": "Fwd",
    "mic": "Search",
}

ALIASES = {
    "on": "power-on",
    "off": "power-off",
    "power": "power-off",
    "select": "ok",
    "enter": "ok",
    "play": "play-pause",
    "pause": "play-pause",
    "rev": "rewind",
    "previous": "rewind",
    "prev": "rewind",
    "fwd": "fast-forward",
    "next": "fast-forward",
    "voice": "mic",
}


class RokuClient:
    def __init__(self, host: str, timeout: float = 3.0):
        self.host = normalize_host(host)
        self.timeout = timeout
        self.base_url = f"http://{self.host}:8060"

    def _request(self, path: str, method: str = "GET") -> bytes:
        request = Request(f"{self.base_url}{path}", method=method)
        if method == "POST":
            request.data = b""
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as exc:
            raise RokuResponseError(
                f"Roku returned HTTP {exc.code} for {path}"
            ) from exc
        except (URLError, TimeoutError, socket.timeout, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise RokuConnectionError(
                f"Could not reach Roku at {self.host}: {reason}"
            ) from exc

    def _get_xml(self, path: str) -> ET.Element:
        data = self._request(path)
        try:
            return ET.fromstring(data)
        except ET.ParseError as exc:
            raise RokuResponseError(f"Roku returned invalid XML for {path}") from exc

    def device_info(self) -> DeviceInfo:
        root = self._get_xml("/query/device-info")

        def text(name: str) -> str:
            return (root.findtext(name) or "").strip()

        name = (
            text("user-device-name")
            or text("friendly-device-name")
            or text("default-device-name")
            or text("model-name")
            or self.host
        )
        return DeviceInfo(
            host=self.host,
            name=name,
            model=text("model-name"),
            serial_number=text("serial-number"),
        )

    def keypress(self, key: str) -> None:
        self._request(f"/keypress/{quote(key, safe='')}", method="POST")

    def keydown(self, key: str) -> None:
        self._request(f"/keydown/{quote(key, safe='')}", method="POST")

    def keyup(self, key: str) -> None:
        self._request(f"/keyup/{quote(key, safe='')}", method="POST")

    def hold_key(self, key: str, seconds: float) -> None:
        self.keydown(key)
        try:
            time.sleep(seconds)
        finally:
            self.keyup(key)

    def command(self, command: str) -> None:
        canonical = ALIASES.get(command.lower(), command.lower())
        try:
            key = KEYS[canonical]
        except KeyError as exc:
            raise RokuError(f"Unknown command: {command}") from exc
        self.keypress(key)

    def installed_apps(self) -> list[tuple[str, str]]:
        root = self._get_xml("/query/apps")
        apps: list[tuple[str, str]] = []
        for app in root.findall("app"):
            app_id = (app.get("id") or "").strip()
            name = (app.text or "").strip()
            if app_id and name:
                apps.append((app_id, name))
        return apps

    def launch_app(self, app_id: str) -> None:
        self._request(f"/launch/{quote(app_id, safe='')}", method="POST")

    def launch_netflix(self) -> None:
        self.launch_named_app("Netflix")

    def launch_youtube(self) -> None:
        self.launch_named_app("YouTube")

    def launch_named_app(self, app_name: str) -> None:
        matches = [
            (app_id, name)
            for app_id, name in self.installed_apps()
            if name.casefold() == app_name.casefold()
        ]
        if not matches:
            raise RokuError(f"{app_name} is not installed on this Roku")
        self.launch_app(matches[0][0])


def normalize_host(host: str) -> str:
    value = host.strip()
    if value.startswith(("http://", "https://")):
        from urllib.parse import urlsplit

        parsed = urlsplit(value)
        value = parsed.hostname or ""
    if not value:
        raise RokuError("A Roku hostname or IP address is required")
    if "/" in value or value.count(":") > 1:
        raise RokuError(f"Invalid Roku hostname or IP address: {host}")
    if ":" in value:
        value = value.rsplit(":", 1)[0]
    return value
