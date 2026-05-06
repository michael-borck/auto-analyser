from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml


@dataclass
class AnalyserConfig:
    type: Literal["http", "cli"]
    url: str | None = None       # for type=http
    command: str | None = None   # for type=cli
    formats: list[str] = field(default_factory=list)


@dataclass
class FamilyConfig:
    analysers: dict[str, AnalyserConfig]

    def get(self, analyser_name: str) -> AnalyserConfig | None:
        return self.analysers.get(analyser_name)

    def available(self) -> list[str]:
        return list(self.analysers.keys())


_DEFAULTS: dict[str, dict] = {
    "document-analyser":  {"type": "http", "url": "http://localhost:8000"},
    "speech-analyser":    {"type": "http", "url": "http://localhost:8001"},
    "video-analyser":     {"type": "http", "url": "http://localhost:8002"},
    "records-analyser":   {"type": "http", "url": "http://localhost:8003"},
    "code-analyser":      {"type": "http", "url": "http://localhost:8004"},
    "wordpress-analyser": {"type": "http", "url": "http://localhost:8005"},
}

_CONFIG_PATHS = [
    Path("auto-analyser.yaml"),
    Path.home() / ".config" / "auto-analyser" / "config.yaml",
]


def load_config() -> FamilyConfig:
    """Load family config. Falls back to built-in defaults if no file found."""
    raw: dict = {}

    for path in _CONFIG_PATHS:
        if path.exists():
            with open(path) as f:
                raw = yaml.safe_load(f) or {}
            break

    merged = {**_DEFAULTS, **raw.get("analysers", {})}
    analysers = {}
    for name, cfg in merged.items():
        if "type" not in cfg:
            raise ValueError(
                f"Analyser '{name}' in config is missing required field 'type'. "
                f"Must be 'http' or 'cli'."
            )
        analysers[name] = AnalyserConfig(
            type=cfg["type"],
            url=cfg.get("url"),
            command=cfg.get("command"),
            formats=cfg.get("formats", []),
        )

    return FamilyConfig(analysers=analysers)
