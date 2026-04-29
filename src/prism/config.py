from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml


@dataclass
class LensConfig:
    type: Literal["http", "cli"]
    url: str | None = None       # for type=http
    command: str | None = None   # for type=cli
    formats: list[str] = field(default_factory=list)


@dataclass
class FamilyConfig:
    lenses: dict[str, LensConfig]

    def get(self, lens_name: str) -> LensConfig | None:
        return self.lenses.get(lens_name)

    def available(self) -> list[str]:
        return list(self.lenses.keys())


_DEFAULTS: dict[str, dict] = {
    "document-lens": {"type": "http", "url": "http://localhost:8000"},
    "audio-lens":    {"type": "cli", "command": "audio-lens"},
    "data-lens":     {"type": "cli", "command": "data-lens"},
    "code-lens":     {"type": "http", "url": "http://localhost:8001"},
    "video-lens":    {"type": "cli", "command": "video-lens"},
}

_CONFIG_PATHS = [
    Path("prism.yaml"),
    Path.home() / ".config" / "prism" / "config.yaml",
]


def load_config() -> FamilyConfig:
    """Load family config. Falls back to built-in defaults if no file found."""
    raw: dict = {}

    for path in _CONFIG_PATHS:
        if path.exists():
            with open(path) as f:
                raw = yaml.safe_load(f) or {}
            break

    # Merge with defaults (file wins over defaults)
    merged = {**_DEFAULTS, **raw.get("lenses", {})}
    lenses = {
        name: LensConfig(
            type=cfg["type"],
            url=cfg.get("url"),
            command=cfg.get("command"),
            formats=cfg.get("formats", []),
        )
        for name, cfg in merged.items()
    }

    return FamilyConfig(lenses=lenses)
