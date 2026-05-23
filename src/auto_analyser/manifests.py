"""Manifest discovery: build the routing table from analyser manifests.

Each analyser exposes a capability manifest via `GET /manifest` (http) or
`<command> manifest` (cli). auto-analyser queries the analysers in its config to
learn which file extensions they claim and whether they are auto-routable, then
builds the extension -> analyser map from that — instead of a hard-coded table.

All failures are swallowed (return None / skip), so discovery degrades to the
static fallback in detector._ROUTES when services are down or offline.
"""
from __future__ import annotations

import json
import subprocess

from .config import AnalyserConfig, FamilyConfig

_MANIFEST_TIMEOUT = 3.0


def fetch_manifest(cfg: AnalyserConfig, *, timeout: float = _MANIFEST_TIMEOUT) -> dict | None:
    """Fetch one analyser's manifest via its configured transport, or None."""
    try:
        if cfg.type == "http" and cfg.url:
            import httpx

            resp = httpx.get(f"{cfg.url.rstrip('/')}/manifest", timeout=timeout)
            if resp.is_success:
                return resp.json()
        elif cfg.type == "cli" and cfg.command:
            proc = subprocess.run(
                [cfg.command, "manifest"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return json.loads(proc.stdout)
    except Exception:
        return None
    return None


def build_routes(config: FamilyConfig) -> dict[str, str]:
    """extension -> analyser name, from manifests. Auto-routable analysers only.

    Analysers whose manifest declares auto_routable=False (explicit-only content
    lenses, e.g. conversation-analyser) never appear in the routing table.
    """
    routes: dict[str, str] = {}
    for name, cfg in config.analysers.items():
        manifest = fetch_manifest(cfg)
        if not manifest or not manifest.get("auto_routable", True):
            continue
        target = manifest.get("name", name)
        for ext in manifest.get("extensions", []):
            routes.setdefault(str(ext).lower(), target)
    return routes
