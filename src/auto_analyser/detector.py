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


def detect(file_path: Path) -> DetectionResult:
    """Detect which analyser should handle this file."""
    ext = file_path.suffix.lower()
    analyser = _ROUTES.get(ext)

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
