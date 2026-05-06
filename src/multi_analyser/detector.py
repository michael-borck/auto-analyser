from dataclasses import dataclass
from pathlib import Path


@dataclass
class DetectionResult:
    lens: str | None        # None if unknown
    extension: str
    warning: str | None = None


# Extension → lens name
_ROUTES: dict[str, str] = {
    # document-lens
    ".pdf": "document-lens",
    ".docx": "document-lens",
    ".pptx": "document-lens",
    ".txt": "document-lens",
    ".md": "document-lens",
    ".qmd": "document-lens",
    ".rst": "document-lens",
    # audio-lens
    ".mp3": "audio-lens",
    ".wav": "audio-lens",
    ".m4a": "audio-lens",
    ".ogg": "audio-lens",
    ".flac": "audio-lens",
    ".aac": "audio-lens",
    ".opus": "audio-lens",
    # data-lens
    ".csv": "data-lens",
    ".tsv": "data-lens",
    ".xlsx": "data-lens",
    ".xls": "data-lens",
    ".parquet": "data-lens",
    ".sqlite": "data-lens",
    ".db": "data-lens",
    ".sqlite3": "data-lens",
    # data-lens (ambiguous)
    ".json": "data-lens",
    ".yaml": "data-lens",
    ".yml": "data-lens",
    ".xml": "data-lens",
    # code-lens
    ".py": "code-lens",
    ".js": "code-lens",
    ".ts": "code-lens",
    ".tsx": "code-lens",
    ".jsx": "code-lens",
    ".java": "code-lens",
    ".c": "code-lens",
    ".cpp": "code-lens",
    ".h": "code-lens",
    ".rb": "code-lens",
    ".php": "code-lens",
    ".go": "code-lens",
    ".rs": "code-lens",
    ".html": "code-lens",
    ".css": "code-lens",
    ".scss": "code-lens",
    ".sql": "code-lens",
    ".ipynb": "code-lens",
    # video-lens
    ".mp4": "video-lens",
    ".mov": "video-lens",
    ".avi": "video-lens",
    ".webm": "video-lens",
    ".mkv": "video-lens",
}

_AMBIGUOUS_WARNING = (
    "{ext} files may be configuration data or structured datasets. "
    "poly-lens is routing to data-lens. For prose content, use document-lens directly."
)

_NOTEBOOK_WARNING = (
    "{ext} is a notebook format containing both code and prose. "
    "code-lens will analyse the code cells. "
    "Pass extracted prose to document-lens for writing quality analysis."
)


def detect(file_path: Path) -> DetectionResult:
    """Detect which lens should handle this file."""
    ext = file_path.suffix.lower()
    lens = _ROUTES.get(ext)

    warning = None
    if ext in {".json", ".yaml", ".yml", ".xml"}:
        warning = _AMBIGUOUS_WARNING.format(ext=ext.upper())
    elif ext in {".ipynb", ".qmd", ".rmd"}:
        warning = _NOTEBOOK_WARNING.format(ext=ext)
    elif lens is None:
        warning = (
            f"Unknown format: {ext}. "
            f"poly-lens does not know which lens handles this file. "
            f"Use a lens directly or add a mapping to your poly-lens.yaml."
        )

    return DetectionResult(lens=lens, extension=ext, warning=warning)
