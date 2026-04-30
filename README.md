# prism

A meta-router that detects a file's format and sends it to the right analysis lens.

Instead of remembering which tool handles which file type, you run `prism analyse <file>` and prism figures out the rest — routing PDFs to [document-lens](https://github.com/michael-borck/document-lens), audio to [audio-lens](https://github.com/michael-borck/audio-lens), spreadsheets to [data-lens](https://github.com/michael-borck/data-lens), and code to code-lens.

## Install

```bash
pip install prism
```

Requires Python 3.11+. Install the lenses you want to use separately.

## Usage

```bash
# Detect which lens handles a file (no analysis, no network calls)
prism detect report.pdf          # report.pdf -> document-lens
prism detect data.json           # Note: may be config data...  data.json -> data-lens
prism detect notebook.ipynb      # Note: contains code and prose...  notebook.ipynb -> code-lens

# Analyse a file (routes to the right lens automatically)
prism analyse report.pdf
prism analyse recording.mp3 --json

# Force a specific lens
prism analyse data.json --lens document-lens

# Check which lenses are installed / reachable
prism status
```

### Python

```python
from prism import Router

router = Router()
result = router.route("report.pdf")

print(result["routed_to"])   # "document-lens"
print(result["success"])     # True
```

## Supported lenses

| Lens | Type | Handles |
|------|------|---------|
| document-lens | HTTP service | `.pdf` `.docx` `.pptx` `.txt` `.md` `.qmd` `.rst` |
| audio-lens | CLI | `.mp3` `.wav` `.m4a` `.ogg` `.flac` `.aac` `.opus` |
| data-lens | CLI | `.csv` `.tsv` `.xlsx` `.xls` `.json` `.yaml` `.xml` `.sqlite` `.db` `.parquet` |
| code-lens | HTTP service | `.py` `.js` `.ts` `.tsx` `.html` `.css` `.ipynb` and more |
| video-lens | CLI | `.mp4` `.mov` `.avi` `.webm` `.mkv` |

## Configuration

prism ships with built-in defaults (document-lens on `localhost:8000`, audio-lens via CLI, etc.). Override with a config file:

```bash
# Project-local (checked first)
./prism.yaml

# User-global
~/.config/prism/config.yaml
```

Copy `lens-family.example.yaml` from this repo as a starting point.

```yaml
lenses:
  document-lens:
    type: http
    url: http://localhost:8000

  audio-lens:
    type: cli
    command: audio-lens

  data-lens:
    type: cli
    command: data-lens
```

## Ambiguous formats

Some formats are handled by more than one lens depending on intent:

- **JSON / YAML / XML** — routed to data-lens by default; a warning is shown if the file looks like configuration data rather than a dataset. Use `--lens document-lens` to treat it as prose.
- **`.ipynb` / `.qmd`** — routed to code-lens (code analysis); pass extracted prose to document-lens separately for writing quality analysis.
- **`.html`** — routed to code-lens; use `--lens document-lens` to treat it as content.

## Part of the prism family

- [document-lens](https://github.com/michael-borck/document-lens) — PDFs, DOCX, PPTX, Markdown
- [data-lens](https://github.com/michael-borck/data-lens) — CSV, XLSX, SQLite, JSON, YAML
- [audio-lens](https://github.com/michael-borck/audio-lens) — audio transcription and speech metrics
- [prism](https://github.com/michael-borck/prism) — meta-router: detects format and calls the right lens

## License

MIT
