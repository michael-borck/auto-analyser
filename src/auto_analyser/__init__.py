from importlib.metadata import version as _v
from pathlib import Path
from typing import Any

from .manifest import MANIFEST
from .router import Router

__version__ = _v("auto-analyser")
del _v

# auto-analyser is an orchestrator (a router), not a single-format engine — but
# it still honours the family's canonical surface. ``AutoAnalyser`` is a naming
# alias for ``Router`` so ``from auto_analyser import AutoAnalyser`` works like
# every other member; ``analyse()`` is the module-level convenience call.
AutoAnalyser = Router


def analyse(
    file_path: str | Path,
    analyser_name: str | None = None,
    *,
    cascade: bool = True,
) -> dict[str, Any]:
    """Route ``file_path`` to the right analyser and return its result.

    Module-level convenience for the family's canonical call shape — equivalent
    to ``Router().route(file_path)``. The result carries a ``routed_to`` key.
    """
    return Router().route(Path(file_path), analyser_name, cascade=cascade)


__all__ = ["Router", "AutoAnalyser", "analyse", "MANIFEST", "__version__"]
