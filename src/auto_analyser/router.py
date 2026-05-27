import json
import subprocess
from pathlib import Path
from typing import Any

import httpx

from .config import FamilyConfig, load_config
from .detector import detect


class RoutingError(Exception):
    """Raised when auto-analyser cannot route or analyse a file."""


# Cascade rules — when this primary analyser returns a result whose
# `<field>` path satisfies `<predicate>`, also invoke the cascaded member.
# v1 has exactly one rule (image-analyser → diagram-analyser); easy to extend.
_CASCADE_RULES: list[dict] = [
    {
        "primary": "image-analyser",
        "trigger_path": ("diagram", "is_diagram"),
        "predicate": lambda v: bool(v),
        "cascade_to": "diagram-analyser",
    },
]


# Named preset bundles — declarative parallel composition.
# Each preset invokes its members on the same file and aggregates results;
# members that can't handle the input are reported gracefully (never raise).
# See lens-analysers/docs/ASSESSMENT-MAP.md for the assessment-design rationale
# behind each named bundle.
_PRESETS: dict[str, list[str]] = {
    "skill-with-evidence": [
        "code-analyser",
        "git-analyser",
        "provenance-analyser",
    ],
    "authentic-essay": [
        "document-analyser",
        "provenance-analyser",
        "revision-analyser",
        "reflection-analyser",
    ],
    # design-with-rationale lists both diagram and site — one will apply
    # to any given input; the other reports a graceful 'unsupported format'.
    "design-with-rationale": [
        "diagram-analyser",
        "site-analyser",
        "provenance-analyser",
        "reflection-analyser",
    ],
    "multimedia-evidence": [
        "video-analyser",
        "speech-analyser",
        "image-analyser",
        "provenance-analyser",
    ],
    "reflective-practice": [
        "reflection-analyser",
        "conversation-analyser",
        "revision-analyser",
    ],
}


def list_presets() -> dict[str, list[str]]:
    """Return a copy of the preset table — name → list of member names."""
    return {k: list(v) for k, v in _PRESETS.items()}


def _get_path(data: dict, path: tuple[str, ...]):
    """Walk a dotted path through nested dicts; return None if any hop is missing."""
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
        if cur is None:
            return None
    return cur


class Router:
    """Routes a file to the appropriate analyser and returns the analysis."""

    def __init__(self, config: FamilyConfig | None = None, *, cascade: bool = True) -> None:
        self._config = config or load_config()
        self._routes: dict[str, str] | None = None
        self._cascade_default = cascade

    def _get_routes(self) -> dict[str, str]:
        """Manifest-derived routing table (falls back to static _ROUTES), cached."""
        if self._routes is None:
            from .detector import resolve_routes

            self._routes = resolve_routes(self._config)
        return self._routes

    def route(
        self,
        file_path: "Path | str",
        analyser_name: str | None = None,
        *,
        cascade: bool | None = None,
    ) -> dict[str, Any]:
        """Analyse a file by routing to the appropriate analyser.

        Returns the analysis dict with a 'routed_to' key injected. When
        cascade is True (default), a configured downstream analyser whose
        trigger predicate matches the primary result is also invoked and its
        result attached under a `cascade` key (never raises — failures land
        in `cascade.error`).

        Raises:
            RoutingError: if the file is missing, format unknown, analyser not
                          configured, or the primary analyser returns an error.
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        if not file_path.exists():
            raise RoutingError(f"File not found: {file_path}")
        if not file_path.is_file():
            raise RoutingError(f"Not a file: {file_path}")

        warning = None

        if analyser_name is None:
            detection = detect(file_path, routes=self._get_routes())
            if detection.analyser is None:
                raise RoutingError(
                    f"Unknown format: {file_path.suffix}. "
                    f"Use --analyser to specify an analyser directly."
                )
            analyser_name = detection.analyser
            warning = detection.warning

        analyser_cfg = self._config.get(analyser_name)
        if analyser_cfg is None:
            raise RoutingError(
                f"Analyser '{analyser_name}' is not configured. "
                f"Available: {self._config.available()}"
            )

        if analyser_cfg.type == "cli":
            if not analyser_cfg.command:
                raise RoutingError(
                    f"Analyser '{analyser_name}' has type=cli but no command configured."
                )
            data = self._call_cli(analyser_cfg.command, file_path)
        elif analyser_cfg.type == "http":
            if not analyser_cfg.url:
                raise RoutingError(
                    f"Analyser '{analyser_name}' has type=http but no url configured."
                )
            data = self._call_http(analyser_cfg.url, file_path)
        else:
            raise RoutingError(f"Unknown analyser type: {analyser_cfg.type}")

        data["routed_to"] = analyser_name
        if warning:
            data["warning"] = warning

        if (cascade if cascade is not None else self._cascade_default):
            cascade_result = self._maybe_cascade(analyser_name, data, file_path)
            if cascade_result is not None:
                data["cascade"] = cascade_result

        return data

    def run_preset(
        self,
        preset_name: str,
        file_path: "Path | str",
    ) -> dict[str, Any]:
        """Invoke every member in a named preset against the same file.

        Returns:
            {
              "preset": "<name>",
              "members": {
                "<member>": <result dict> OR {"error": "..."},
                ...
              },
              "flags_across_bundle": ["<member>:<flag>", ...]
            }

        A failed member (unconfigured, unreachable, unsupported format) reports
        its error in `members[<name>]['error']` rather than failing the bundle.
        Cascade routing is NOT applied inside presets — presets are explicit
        composition; cascade is implicit. Mixing them produces surprises.

        Raises:
            RoutingError: only for input-level problems (unknown preset, file
                          missing). Per-member failures never raise.
        """
        if preset_name not in _PRESETS:
            raise RoutingError(
                f"Unknown preset: {preset_name!r}. "
                f"Available: {sorted(_PRESETS)}"
            )

        if isinstance(file_path, str):
            file_path = Path(file_path)
        if not file_path.exists():
            raise RoutingError(f"File not found: {file_path}")
        if not file_path.is_file():
            raise RoutingError(f"Not a file: {file_path}")

        member_results: dict[str, Any] = {}
        flags_across: list[str] = []

        for member in _PRESETS[preset_name]:
            cfg = self._config.get(member)
            if cfg is None:
                member_results[member] = {"error": "not configured"}
                continue
            try:
                if cfg.type == "cli":
                    if not cfg.command:
                        member_results[member] = {"error": "type=cli but no command configured"}
                        continue
                    data = self._call_cli(cfg.command, file_path)
                elif cfg.type == "http":
                    if not cfg.url:
                        member_results[member] = {"error": "type=http but no url configured"}
                        continue
                    data = self._call_http(cfg.url, file_path)
                else:
                    member_results[member] = {"error": f"unknown analyser type: {cfg.type}"}
                    continue
                member_results[member] = data
                # Roll up flags. Members emit them in different shapes:
                #  - `flags`: list[str]                 (git/spreadsheet/site/etc.)
                #  - `suspicious_flags`: list[str]      (git-analyser legacy field)
                #  - `diagram.is_diagram`: bool         (image-analyser cascade hint)
                # For v1 we only flatten the `flags` list; other shapes can be
                # added as patterns emerge.
                if isinstance(data, dict):
                    for flag in data.get("flags") or []:
                        flags_across.append(f"{member}:{flag}")
            except RoutingError as e:
                member_results[member] = {"error": str(e)}

        return {
            "preset": preset_name,
            "members": member_results,
            "flags_across_bundle": flags_across,
        }

    def _maybe_cascade(
        self,
        primary_name: str,
        primary_data: dict[str, Any],
        file_path: Path,
    ) -> dict[str, Any] | None:
        """Apply the first matching cascade rule. Returns the cascade block, or None.

        Never raises — a failed cascade is reported, not propagated, so the
        primary result is always preserved.
        """
        for rule in _CASCADE_RULES:
            if rule["primary"] != primary_name:
                continue
            trigger_value = _get_path(primary_data, rule["trigger_path"])
            if not rule["predicate"](trigger_value):
                continue
            cascade_to = rule["cascade_to"]
            block: dict[str, Any] = {
                "triggered_by": f"{rule['primary']}." + ".".join(rule["trigger_path"]),
                "routed_to": cascade_to,
            }
            target_cfg = self._config.get(cascade_to)
            if target_cfg is None:
                block["error"] = f"cascade target {cascade_to!r} is not configured"
                return block
            try:
                if target_cfg.type == "cli":
                    if not target_cfg.command:
                        block["error"] = f"{cascade_to} has type=cli but no command configured"
                        return block
                    block["result"] = self._call_cli(target_cfg.command, file_path)
                elif target_cfg.type == "http":
                    if not target_cfg.url:
                        block["error"] = f"{cascade_to} has type=http but no url configured"
                        return block
                    block["result"] = self._call_http(target_cfg.url, file_path)
                else:
                    block["error"] = f"unknown analyser type: {target_cfg.type}"
            except RoutingError as e:
                block["error"] = str(e)
            return block
        return None

    def _call_cli(self, command: str, file_path: Path) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                [command, str(file_path), "--json"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if proc.returncode != 0:
                try:
                    err = json.loads(proc.stderr)
                    msg = err.get("error", proc.stderr.strip())
                except (json.JSONDecodeError, AttributeError):
                    msg = proc.stderr.strip() or f"{command} exited with code {proc.returncode}"
                raise RoutingError(msg)
            try:
                return json.loads(proc.stdout)
            except json.JSONDecodeError as e:
                raise RoutingError(
                    f"{command} returned invalid JSON: {e}. "
                    f"stdout={proc.stdout[:200]!r}"
                )
        except FileNotFoundError:
            raise RoutingError(f"CLI tool '{command}' not found. Is it installed?")
        except RoutingError:
            raise
        except Exception as e:
            raise RoutingError(str(e)) from e

    def _call_http(self, url: str, file_path: Path) -> dict[str, Any]:
        """POST file to {url}/analyse."""
        try:
            with open(file_path, "rb") as f:
                with httpx.Client(timeout=300) as client:
                    response = client.post(
                        f"{url}/analyse",
                        files={"file": (file_path.name, f)},
                    )
            if not response.is_success:
                try:
                    detail = response.json().get("detail", response.text)
                except Exception:
                    detail = response.text
                raise RoutingError(f"HTTP {response.status_code}: {detail}")
            return response.json()
        except httpx.ConnectError:
            raise RoutingError(f"Cannot connect to {url}. Is the service running?")
        except RoutingError:
            raise
        except Exception as e:
            raise RoutingError(str(e)) from e
