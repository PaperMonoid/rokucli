"""Command-line interface for rokucli."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from .client import ALIASES, KEYS, DeviceInfo, RokuClient, RokuError
from .config import load_host, save_host
from .discovery import discover_with_fallback


COMMANDS = tuple(KEYS) + ("netflix", "youtube")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="roku",
        description="Discover and control Roku devices on your local network.",
    )
    result.add_argument(
        "--device",
        metavar="HOST",
        help="use this Roku hostname or IP instead of the saved device",
    )
    result.add_argument(
        "--timeout",
        metavar="SECONDS",
        type=float,
        default=3.0,
        help="network timeout (default: 3)",
    )
    result.add_argument(
        "--seconds",
        type=float,
        metavar="SECONDS",
        help="hold the mic button for this many seconds",
    )
    result.add_argument(
        "--network",
        metavar="CIDR",
        help="fallback network to scan, for example 192.168.1.0/24",
    )
    result.add_argument(
        "command",
        nargs="?",
        help="remote command, or scan/select (omit for interactive mode)",
    )
    return result


def find_devices(
    timeout: float,
    *,
    network: str | None = None,
    discover_fn: Callable = discover_with_fallback,
    client_factory: Callable[..., RokuClient] = RokuClient,
) -> list[DeviceInfo]:
    devices: list[DeviceInfo] = []
    for endpoint in discover_fn(timeout=timeout, cidr=network):
        try:
            devices.append(client_factory(endpoint.host, timeout=timeout).device_info())
        except RokuError:
            devices.append(DeviceInfo(host=endpoint.host, name=endpoint.host))
    return devices


def print_devices(devices: Sequence[DeviceInfo]) -> None:
    if not devices:
        print("No Roku devices found.")
        return
    for index, device in enumerate(devices, start=1):
        detail = f" — {device.model}" if device.model else ""
        print(f"{index}. {device.name} ({device.host}){detail}")


def select_device(
    timeout: float,
    *,
    network: str | None = None,
    input_fn: Callable[[str], str] = input,
    discover_fn: Callable = discover_with_fallback,
    client_factory: Callable[..., RokuClient] = RokuClient,
) -> str:
    devices = find_devices(
        timeout,
        network=network,
        discover_fn=discover_fn,
        client_factory=client_factory,
    )
    if not devices:
        raise RokuError(
            "No Roku devices found. Check that both devices are on the same network."
        )
    print_devices(devices)
    if len(devices) == 1:
        selected = devices[0]
    else:
        try:
            choice = input_fn("Select a Roku: ").strip()
            index = int(choice)
            if index < 1 or index > len(devices):
                raise ValueError
            selected = devices[index - 1]
        except (ValueError, IndexError) as exc:
            raise RokuError("Invalid device selection") from exc
    save_host(selected.host)
    print(f"Selected {selected.name} ({selected.host})")
    return selected.host


def resolve_host(
    explicit_host: str | None,
    timeout: float,
    *,
    network: str | None = None,
    input_fn: Callable[[str], str] = input,
) -> str:
    if explicit_host:
        return explicit_host
    saved = load_host()
    if saved:
        try:
            RokuClient(saved, timeout=timeout).device_info()
            return saved
        except RokuError:
            print(f"Saved Roku at {saved} is unavailable; scanning again.", file=sys.stderr)
    return select_device(timeout, network=network, input_fn=input_fn)


def send_command(
    client: RokuClient,
    command: str,
    *,
    mic_seconds: float | None = None,
) -> None:
    canonical = ALIASES.get(command.lower(), command.lower())
    if canonical == "netflix":
        client.launch_netflix()
    elif canonical == "youtube":
        client.launch_youtube()
    elif canonical == "mic" and mic_seconds is not None:
        client.hold_key("Search", mic_seconds)
    else:
        client.command(canonical)


def interactive(client: RokuClient, *, input_fn: Callable[[str], str] = input) -> None:
    print(f"Connected to {client.device_info().name} ({client.host})")
    print("Commands: " + ", ".join(COMMANDS))
    print("Use 'mic SECONDS' to hold the voice button.")
    print("Type help for aliases, or quit to exit.")
    while True:
        try:
            raw = input_fn("roku> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not raw:
            continue
        command = raw.lower()
        if command in {"quit", "exit", "q"}:
            return
        if command in {"help", "?"}:
            print("Commands: " + ", ".join(COMMANDS))
            print("Timed mic: mic SECONDS (example: mic 5)")
            print("Aliases: " + ", ".join(f"{a}={c}" for a, c in ALIASES.items()))
            continue
        try:
            parts = command.split()
            if len(parts) == 2 and ALIASES.get(parts[0], parts[0]) == "mic":
                try:
                    seconds = float(parts[1])
                except ValueError as exc:
                    raise RokuError("Mic duration must be a number") from exc
                if seconds <= 0:
                    raise RokuError("Mic duration must be greater than zero")
                send_command(client, parts[0], mic_seconds=seconds)
            elif len(parts) > 1:
                raise RokuError(f"Unknown command: {command}")
            else:
                send_command(client, command)
        except RokuError as exc:
            print(f"Error: {exc}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.timeout <= 0:
        print("Error: --timeout must be greater than zero", file=sys.stderr)
        return 2
    if args.seconds is not None and args.seconds <= 0:
        print("Error: --seconds must be greater than zero", file=sys.stderr)
        return 2

    try:
        command = args.command.lower() if args.command else None
        canonical = ALIASES.get(command, command) if command else None
        if args.seconds is not None and canonical != "mic":
            raise RokuError("--seconds can only be used with the mic command")
        if command == "scan":
            print_devices(find_devices(args.timeout, network=args.network))
            return 0
        if command == "select":
            select_device(args.timeout, network=args.network)
            return 0
        if command and command not in COMMANDS and command not in ALIASES:
            choices = ", ".join(COMMANDS)
            raise RokuError(f"Unknown command '{command}'. Available commands: {choices}")

        host = resolve_host(args.device, args.timeout, network=args.network)
        client = RokuClient(host, timeout=args.timeout)
        if command:
            send_command(client, command, mic_seconds=args.seconds)
        else:
            interactive(client)
        return 0
    except (RokuError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
