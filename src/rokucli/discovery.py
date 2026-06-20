"""Discover Roku devices with SSDP."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import ipaddress
import socket
import time
from urllib.parse import urlsplit
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET


SSDP_ADDRESS = ("239.255.255.250", 1900)
SSDP_REQUEST = (
    "M-SEARCH * HTTP/1.1\r\n"
    "Host: 239.255.255.250:1900\r\n"
    'Man: "ssdp:discover"\r\n'
    "ST: roku:ecp\r\n"
    "\r\n"
).encode("ascii")


@dataclass(frozen=True)
class DiscoveredDevice:
    host: str
    location: str


def parse_ssdp_response(data: bytes) -> dict[str, str]:
    """Parse case-insensitive HTTP-style SSDP headers."""
    text = data.decode("iso-8859-1", errors="replace")
    headers: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    return headers


def discover(timeout: float = 2.5) -> list[DiscoveredDevice]:
    """Return unique Roku ECP endpoints responding before timeout."""
    found: dict[str, DiscoveredDevice] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.bind(("", 0))
        sock.settimeout(min(timeout, 0.25))
        sock.sendto(SSDP_REQUEST, SSDP_ADDRESS)
        deadline = time.monotonic() + timeout
        next_retry = time.monotonic() + min(1.0, timeout / 2)

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if time.monotonic() >= next_retry:
                sock.sendto(SSDP_REQUEST, SSDP_ADDRESS)
                next_retry = deadline + 1
            sock.settimeout(min(remaining, 0.25))
            try:
                data, address = sock.recvfrom(65535)
            except socket.timeout:
                continue

            headers = parse_ssdp_response(data)
            location = headers.get("location")
            if not location:
                continue
            parsed = urlsplit(location)
            host = parsed.hostname or address[0]
            if host:
                found[host] = DiscoveredDevice(host=host, location=location)
    finally:
        sock.close()

    return sorted(found.values(), key=lambda item: item.host)


def local_ipv4() -> str:
    """Determine the IPv4 address used for local network traffic."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # UDP connect selects a route without transmitting application data.
        sock.connect(SSDP_ADDRESS)
        return sock.getsockname()[0]
    except OSError as exc:
        raise RuntimeError("Could not determine the local IPv4 address") from exc
    finally:
        sock.close()


def fallback_network(cidr: str | None = None) -> ipaddress.IPv4Network:
    """Return an explicitly configured network or a conservative local /24."""
    if cidr:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError as exc:
            raise ValueError(f"Invalid IPv4 network: {cidr}") from exc
        if not isinstance(network, ipaddress.IPv4Network):
            raise ValueError("Only IPv4 networks are supported")
    else:
        network = ipaddress.ip_network(f"{local_ipv4()}/24", strict=False)

    if network.num_addresses > 1024:
        raise ValueError(
            f"Network {network} is too large to scan; use a /22 or smaller network"
        )
    return network


def _is_roku(host: str, timeout: float) -> bool:
    try:
        with urlopen(
            f"http://{host}:8060/query/device-info",
            timeout=timeout,
        ) as response:
            root = ET.fromstring(response.read())
    except (HTTPError, URLError, TimeoutError, socket.timeout, OSError, ET.ParseError):
        return False
    return root.tag == "device-info"


def discover_by_http(
    timeout: float = 0.35,
    *,
    cidr: str | None = None,
    max_workers: int = 32,
) -> list[DiscoveredDevice]:
    """Probe a bounded local IPv4 network for Roku ECP endpoints."""
    network = fallback_network(cidr)
    hosts = [str(address) for address in network.hosts()]
    found: list[DiscoveredDevice] = []

    with ThreadPoolExecutor(max_workers=min(max_workers, len(hosts) or 1)) as executor:
        futures = {
            executor.submit(_is_roku, host, timeout): host
            for host in hosts
        }
        for future in as_completed(futures):
            host = futures[future]
            if future.result():
                found.append(
                    DiscoveredDevice(
                        host=host,
                        location=f"http://{host}:8060/",
                    )
                )

    return sorted(found, key=lambda item: ipaddress.ip_address(item.host))


def discover_with_fallback(
    timeout: float = 2.5,
    *,
    cidr: str | None = None,
) -> list[DiscoveredDevice]:
    """Use SSDP first, then probe the local network if multicast is silent."""
    devices = discover(timeout)
    if devices:
        return devices
    return discover_by_http(cidr=cidr)
