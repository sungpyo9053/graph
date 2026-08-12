from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(str(bundled))
    return Path(__file__).resolve().parents[2]


def default_verified_urls_path() -> Path:
    return resource_root() / "verified-urls.json"


def default_output_path(configured: str) -> Path:
    path = Path(configured).expanduser()
    if is_frozen_app() and not path.is_absolute():
        return Path.home() / "Documents" / "IdeaDiscoveryGraph" / path
    return path


def prepare_desktop_environment() -> None:
    """Make a Finder-launched bundle behave like the terminal entrypoint."""
    os.environ.setdefault("LLM_PROVIDER", "codex")
    candidates = (
        Path.home() / ".local" / "bin",
        Path.home() / ".cargo" / "bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    )
    current = os.environ.get("PATH", "")
    prefixes = [str(item) for item in candidates if item.is_dir()]
    os.environ["PATH"] = os.pathsep.join([*prefixes, current])
