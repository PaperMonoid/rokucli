"""Persist the selected Roku endpoint."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .client import RokuError


def config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "rokucli" / "config.json"


def load_host(path: Path | None = None) -> str | None:
    target = path or config_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise RokuError(f"Could not read configuration at {target}: {exc}") from exc
    host = data.get("host")
    return host if isinstance(host, str) and host else None


def save_host(host: str, path: Path | None = None) -> None:
    target = path or config_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"host": host}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise RokuError(f"Could not save configuration at {target}: {exc}") from exc

