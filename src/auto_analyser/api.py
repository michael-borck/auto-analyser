"""FastAPI HTTP surface for auto-analyser — the orchestrator's routing endpoint.

`POST /analyse` accepts any file, detects its format, forwards it to the right
family member (over HTTP or CLI per config), and returns that member's analysis
with a `routed_to` key. `GET /health` + `GET /manifest` come from lens-contract.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from lens_contract import add_contract_routes, add_cors, upload_tempfile

from .manifest import MANIFEST
from .router import Router, RoutingError, list_presets

app = FastAPI(title="auto-analyser", version=MANIFEST["version"])

# GET /health and GET /manifest (the family contract, via lens-contract).
add_contract_routes(app, MANIFEST)
# CORS — env-driven: AUTO_ANALYSER_MODE=desktop (Electron) or AUTO_ANALYSER_ALLOWED_ORIGINS.
add_cors(app, env_prefix="AUTO_ANALYSER")

_router = Router()


@app.post("/analyse")
async def analyse(
    file: UploadFile = File(...),
    cascade: bool = True,
    preset: str | None = None,
) -> dict[str, Any]:
    """Route an uploaded file to the right analyser and return its result.

    Three modes (in precedence order):
    1. `preset=<name>` — invoke a named bundle (see GET /presets), aggregate.
       `cascade` is ignored in this mode (off inside presets by design).
    2. Default — auto-detect format, route to one member, optionally cascade
       to a downstream member when the primary result satisfies a cascade
       rule's trigger.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Empty file")

    # The upload's suffix drives detection, so upload_tempfile (which preserves it)
    # is what lets the router pick the right downstream analyser.
    with upload_tempfile(content, file.filename) as tmp_path:
        try:
            if preset:
                return _router.run_preset(preset, tmp_path)
            return _router.route(tmp_path, cascade=cascade)
        except RoutingError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/presets")
async def presets() -> dict[str, Any]:
    """Return the named preset bundles — name → list of member names."""
    return {"presets": list_presets()}
