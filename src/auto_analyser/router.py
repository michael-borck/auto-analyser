import json
import subprocess
from pathlib import Path
from typing import Any

import httpx

from .config import FamilyConfig, load_config
from .detector import detect


class RoutingError(Exception):
    """Raised when auto-analyser cannot route or analyse a file."""


class Router:
    """Routes a file to the appropriate analyser and returns the analysis."""

    def __init__(self, config: FamilyConfig | None = None) -> None:
        self._config = config or load_config()

    def route(
        self,
        file_path: "Path | str",
        analyser_name: str | None = None,
    ) -> dict[str, Any]:
        """Analyse a file by routing to the appropriate analyser.

        Returns the analysis dict with a 'routed_to' key injected.

        Raises:
            RoutingError: if the file is missing, format unknown, analyser not
                          configured, or the analyser returns an error.
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        if not file_path.exists():
            raise RoutingError(f"File not found: {file_path}")
        if not file_path.is_file():
            raise RoutingError(f"Not a file: {file_path}")

        warning = None

        if analyser_name is None:
            detection = detect(file_path)
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
        return data

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
