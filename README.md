# rokucli

A lightweight command-line remote for Roku devices on your local network.

`rokucli` discovers Roku players and TVs, remembers your selected device, sends
remote-control commands, and launches Netflix or YouTube. It is implemented
entirely with the Python standard library.

## Features

- Discovers Roku devices with SSDP
- Falls back to scanning a bounded local IPv4 network
- Saves the selected Roku for later commands
- Supports navigation, playback, power, and search/voice-button commands
- Launches installed Netflix and YouTube apps by looking up their app IDs
- Provides both one-shot commands and an interactive shell

## Requirements

- Python 3.10 or newer
- A Roku device reachable on the same local network
- Network access to the Roku External Control Protocol (ECP) on port `8060`

## Run from source

Clone the repository and run the package from the repository root:

```bash
git clone https://github.com/PaperMonoid/rokucli.git
cd rokucli
python3 -m src.rokucli scan
```

There are no third-party runtime dependencies.

For convenience, you can define a shell alias while working from the repository:

```bash
alias roku='python3 -m src.rokucli'
```

## Quick start

Find Roku devices:

```bash
python3 -m src.rokucli scan
```

Select and save a device:

```bash
python3 -m src.rokucli select
```

Send a command:

```bash
python3 -m src.rokucli home
python3 -m src.rokucli play-pause
python3 -m src.rokucli netflix
```

Start interactive mode by omitting the command:

```bash
python3 -m src.rokucli
```

```text
Connected to Living Room (192.168.1.42)
Commands: home, back, power-on, power-off, up, down, left, right, ...
roku> home
roku> netflix
roku> quit
```

On the first command, `rokucli` automatically scans for devices if none has
been selected. If it finds more than one, it prompts you to choose.

## Commands

| Command | Action |
| --- | --- |
| `home` | Go to the Roku home screen |
| `back` | Go back |
| `power-on` | Turn the device on |
| `power-off` | Turn the device off |
| `up`, `down`, `left`, `right` | Navigate |
| `ok` | Select the focused item |
| `play-pause` | Toggle playback |
| `rewind` | Rewind or skip backward |
| `fast-forward` | Fast-forward or skip ahead |
| `mic` | Press the Roku search/voice button |
| `netflix` | Launch Netflix if installed |
| `youtube` | Launch YouTube if installed |
| `scan` | List discovered Roku devices |
| `select` | Discover, select, and save a Roku |

Available aliases:

| Alias | Command |
| --- | --- |
| `on` | `power-on` |
| `off`, `power` | `power-off` |
| `select`, `enter` | `ok` |
| `play`, `pause` | `play-pause` |
| `rev`, `previous`, `prev` | `rewind` |
| `fwd`, `next` | `fast-forward` |
| `voice` | `mic` |

### Timed mic button

Hold the search/voice button for a specific duration:

```bash
python3 -m src.rokucli mic --seconds 5
```

In interactive mode, use:

```text
roku> mic 5
```

The key-up event is still sent if the command is interrupted.

## Options

```text
--device HOST       Use a hostname or IP instead of the saved device
--timeout SECONDS   Set the network timeout (default: 3)
--seconds SECONDS   Hold the mic button for this duration
--network CIDR      Set the fallback network to scan
```

Examples:

```bash
# Control a device without changing the saved selection
python3 -m src.rokucli --device 192.168.1.42 home

# Scan a specific subnet when multicast discovery is unavailable
python3 -m src.rokucli --network 192.168.1.0/24 scan

# Allow more time for device discovery
python3 -m src.rokucli --timeout 5 select
```

Fallback scans are limited to IPv4 networks with no more than 1,024 addresses
(`/22` or smaller).

## Configuration

The selected device is stored as JSON in:

- Linux and other Unix-like systems:
  `$XDG_CONFIG_HOME/rokucli/config.json`, or
  `~/.config/rokucli/config.json` when `XDG_CONFIG_HOME` is unset
- Windows: `%APPDATA%\rokucli\config.json`

Run `select` again at any time to replace the saved device. If a saved Roku is
unavailable, `rokucli` automatically starts discovery again.

## Development

Run the test suite from the repository root:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Troubleshooting

**No Roku devices found**

- Confirm the computer and Roku are on the same local network.
- Check whether client isolation or multicast filtering is enabled on the
  network.
- Try an explicit fallback subnet:
  `python3 -m src.rokucli --network 192.168.1.0/24 scan`.
- If you know the address, bypass discovery with `--device`.

**Netflix or YouTube is reported as not installed**

The app launcher matches the installed app name reported by the Roku. Confirm
that the corresponding app is installed on the selected device.

**Power commands do not work**

Power support depends on the capabilities and settings of the Roku model.

## License

This project is licensed under the [MIT License](LICENSE).
