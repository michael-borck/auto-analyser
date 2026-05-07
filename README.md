# auto-analyser

Routes any file to the right analyser. Detects the file format, calls the appropriate tool, and returns the result — so you don't need to know which analyser handles which format.

Part of the [analyser family](#the-analyser-family).

## Install

```bash
pip install auto-analyser
```

Requires Python 3.11+. The analysers it calls must be installed and reachable separately.

## Usage

### CLI

```bash
# Detect which analyser would handle a file
auto-analyser detect report.pdf       # report.pdf -> document-analyser
auto-analyser detect interview.mp3    # interview.mp3 -> speech-analyser
auto-analyser detect data.xlsx        # data.xlsx -> records-analyser

# Analyse a file — auto-detects format and routes
auto-analyser analyse report.pdf
auto-analyser analyse recording.mp3 --json

# Force a specific analyser
auto-analyser analyse interview.mp4 --analyser speech-analyser

# Check which analysers are reachable
auto-analyser status
```

### Python

```python
from auto_analyser import Router

router = Router()
result = router.route("report.pdf")
print(result["routed_to"])   # "document-analyser"
```

## Configuration

auto-analyser ships with built-in defaults (document-analyser on `localhost:8000`, speech-analyser via CLI, etc.). Override with a YAML config file at `./auto-analyser.yaml` or `~/.config/auto-analyser/config.yaml`:

```yaml
lenses:
  document-analyser:
    type: http
    url: http://localhost:8000
    extensions: [.pdf, .docx, .pptx, .txt, .md]

  speech-analyser:
    type: cli
    command: speech-analyser
    extensions: [.mp3, .wav, .m4a, .ogg, .flac, .mp4, .mov]

  records-analyser:
    type: http
    url: http://localhost:8003
    extensions: [.csv, .tsv, .xlsx, .parquet, .db, .sqlite]
```

## The analyser family

Low-level analysis tools. Each accepts files directly and returns structured JSON. Build your own UI or pipeline on top.

| Package | Handles |
|---|---|
| [speech-analyser](https://github.com/michael-borck/speech-analyser) | audio and video files — transcript and speech metrics |
| [video-analyser](https://github.com/michael-borck/video-analyser) | video files — frames, scenes, and visual quality |
| [document-analyser](https://github.com/michael-borck/document-analyser) | PDF, DOCX, PPTX, TXT — text and readability |
| [code-analyser](https://github.com/michael-borck/code-analyser) | source code — style, complexity, and quality metrics |
| [records-analyser](https://github.com/michael-borck/records-analyser) | CSV, Excel, SQLite, Parquet, JSON — data profiling |
| [auto-analyser](https://github.com/michael-borck/auto-analyser) | any file — detects format and routes to the right tool |

## Licence

MIT
