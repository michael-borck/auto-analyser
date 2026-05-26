from dataclasses import dataclass
from pathlib import Path


@dataclass
class DetectionResult:
    analyser: str | None    # None if unknown
    extension: str
    warning: str | None = None


# Extension → analyser name
_ROUTES: dict[str, str] = {
    # document-analyser
    ".pdf": "document-analyser",
    ".docx": "document-analyser",
    ".pptx": "document-analyser",
    ".txt": "document-analyser",
    ".md": "document-analyser",
    ".qmd": "document-analyser",
    ".rst": "document-analyser",
    # speech-analyser
    ".mp3": "speech-analyser",
    ".wav": "speech-analyser",
    ".m4a": "speech-analyser",
    ".ogg": "speech-analyser",
    ".flac": "speech-analyser",
    ".aac": "speech-analyser",
    ".opus": "speech-analyser",
    # records-analyser
    ".csv": "records-analyser",
    ".tsv": "records-analyser",
    ".xlsx": "records-analyser",
    ".xls": "records-analyser",
    ".parquet": "records-analyser",
    ".sqlite": "records-analyser",
    ".db": "records-analyser",
    ".sqlite3": "records-analyser",
    # records-analyser (ambiguous)
    ".json": "records-analyser",
    ".yaml": "records-analyser",
    ".yml": "records-analyser",
    ".xml": "records-analyser",
    # code-analyser
    ".py": "code-analyser",
    ".js": "code-analyser",
    ".ts": "code-analyser",
    ".tsx": "code-analyser",
    ".jsx": "code-analyser",
    ".html": "code-analyser",
    ".css": "code-analyser",
    ".scss": "code-analyser",
    ".sql": "code-analyser",
    ".ipynb": "code-analyser",
    # video-analyser
    ".mp4": "video-analyser",
    ".mov": "video-analyser",
    ".avi": "video-analyser",
    ".webm": "video-analyser",
    ".mkv": "video-analyser",
    # wordpress-analyser
    ".php": "wordpress-analyser",
    # image-analyser
    ".png": "image-analyser",
    ".jpg": "image-analyser",
    ".jpeg": "image-analyser",
    ".gif": "image-analyser",
    ".bmp": "image-analyser",
    ".tiff": "image-analyser",
    ".tif": "image-analyser",
    ".webp": "image-analyser",
    # diagram-analyser (text formats only; image diagrams go to image-analyser →
    # cascade to diagram-analyser when is_diagram=True)
    ".mmd": "diagram-analyser",
    ".mermaid": "diagram-analyser",
    ".puml": "diagram-analyser",
    ".plantuml": "diagram-analyser",
    ".dot": "diagram-analyser",
    ".gv": "diagram-analyser",
    ".drawio": "diagram-analyser",
}

_AMBIGUOUS_WARNING = (
    "{ext} files may be configuration data or structured datasets. "
    "auto-analyser is routing to records-analyser. "
    "For prose content, use document-analyser directly."
)

_NOTEBOOK_WARNING = (
    "{ext} is a notebook format containing both code and prose. "
    "code-analyser will analyse the code cells. "
    "Pass extracted prose to document-analyser for writing quality analysis."
)


def resolve_routes(config) -> dict[str, str]:
    """Merge the static fallback with live manifest-derived routes (manifests win).

    When manifests can't be fetched (offline / services down), this is just
    _ROUTES, so detection behaviour is unchanged.
    """
    from .manifests import build_routes

    return {**_ROUTES, **build_routes(config)}


def detect(file_path: Path, routes: dict[str, str] | None = None) -> DetectionResult:
    """Detect which analyser should handle this file.

    `routes` is the extension->analyser table; defaults to the static _ROUTES
    fallback. The Router passes a manifest-derived table via resolve_routes().
    """
    ext = file_path.suffix.lower()
    table = _ROUTES if routes is None else routes
    analyser = table.get(ext)

    warning = None
    if ext in {".json", ".yaml", ".yml", ".xml"}:
        warning = _AMBIGUOUS_WARNING.format(ext=ext.upper())
    elif ext in {".ipynb", ".qmd", ".rmd"}:
        warning = _NOTEBOOK_WARNING.format(ext=ext)
    elif analyser is None:
        warning = (
            f"Unknown format: {ext}. "
            f"auto-analyser does not know which analyser handles this file. "
            f"Use an analyser directly or add a mapping to your auto-analyser.yaml."
        )

    return DetectionResult(analyser=analyser, extension=ext, warning=warning)
