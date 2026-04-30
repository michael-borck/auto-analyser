from .config import FamilyConfig, load_config
from .detector import detect
import json
import subprocess
from pathlib import Path
from typing import Any

import httpx


class Router:
    """Routes a file to the appropriate lens and returns the result."""

    def __init__(self, config: FamilyConfig | None = None) -> None:
        self._config = config or load_config()

    def route(
        self,
        file_path: "Path | str",
        lens_name: str | None = None,
    ) -> dict[str, Any]:
        """Analyse a file by routing to the appropriate lens."""
        if isinstance(file_path, str):
            file_path = Path(file_path)

        warning = None

        if lens_name is None:
            detection = detect(file_path)
            if detection.lens is None:
                return {
                    "success": False,
                    "error": f"Unknown format: {file_path.suffix}. "
                             f"Use --lens to specify a lens directly.",
                    "data": {},
                }
            lens_name = detection.lens
            warning = detection.warning

        lens_cfg = self._config.get(lens_name)
        if lens_cfg is None:
            return {
                "success": False,
                "error": f"Lens '{lens_name}' is not configured. "
                         f"Available: {self._config.available()}",
                "data": {},
            }

        if lens_cfg.type == "cli":
            result = self._call_cli(lens_cfg.command, file_path)
        elif lens_cfg.type == "http":
            result = self._call_http(lens_cfg.url, file_path)
        else:
            return {"success": False, "error": f"Unknown lens type: {lens_cfg.type}", "data": {}}

        result["routed_to"] = lens_name
        if warning:
            result["warning"] = warning
        return result

    def _call_cli(self, command: str, file_path: Path) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                [command, "analyse", str(file_path), "--json"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if proc.returncode != 0:
                return {
                    "success": False,
                    "error": f"{command} exited with code {proc.returncode}: {proc.stderr}",
                    "data": {},
                }
            return json.loads(proc.stdout)
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"CLI tool '{command}' not found. Is it installed?",
                "data": {},
            }
        except Exception as e:
            return {"success": False, "error": repr(e), "data": {}}

    def _call_http(self, url: str, file_path: Path) -> dict[str, Any]:
        try:
            with open(file_path, "rb") as f:
                with httpx.Client(timeout=300) as client:
                    response = client.post(
                        f"{url}/files",
                        files={"files": (file_path.name, f)},
                    )
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            return {
                "success": False,
                "error": f"Cannot connect to {url}. Is the service running?",
                "data": {},
            }
        except Exception as e:
            return {"success": False, "error": repr(e), "data": {}}
