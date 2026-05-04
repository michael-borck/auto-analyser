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
    "audio-lens":    {"type": "cli",  "command": "audiolens"},
    "data-lens":     {"type": "cli",  "command": "datalens"},
    "code-lens":     {"type": "http", "url": "http://localhost:8003"},
    "video-lens":    {"type": "cli",  "command": "videolens"},
}

_CONFIG_PATHS = [
    Path("poly-lens.yaml"),
    Path.home() / ".config" / "poly-lens" / "config.yaml",
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
    lenses = {}
    for name, cfg in merged.items():
        if "type" not in cfg:
            raise ValueError(f"Lens '{name}' in config is missing required field 'type'. Must be 'http' or 'cli'.")
        lenses[name] = LensConfig(
            type=cfg["type"],
            url=cfg.get("url"),
            command=cfg.get("command"),
            formats=cfg.get("formats", []),
        )

    return FamilyConfig(lenses=lenses)
