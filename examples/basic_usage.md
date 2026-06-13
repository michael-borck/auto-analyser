# auto-analyser — basic usage

auto-analyser is the family orchestrator: it routes a file to the right analyser, can run named preset bundles, and cascades to downstream analysers when a result triggers one.

## Install

```bash
pip install auto-analyser
```

## CLI

```bash
# Auto-route a file to the right analyser
auto-analyser essay.docx --json

# Run a named preset bundle (parallel composition, cascade off inside presets)
auto-analyser essay.docx --preset authentic-essay --json

# List the available preset bundles and their members
auto-analyser presets

# Force a specific analyser, or disable cascade routing
auto-analyser data.csv --analyser records-analyser --json
auto-analyser image.png --no-cascade --json

# Inspect routing without analysing
auto-analyser detect notebook.ipynb

# Check which configured analysers are reachable
auto-analyser status
```

## Python

```python
from auto_analyser import Router

router = Router()

# Auto-route (cascade on by default)
result = router.route("essay.docx")
print(result["routed_to"])

# Run a named preset bundle
bundle = router.run_preset("authentic-essay", "essay.docx")
print(bundle["preset"], list(bundle["members"]))
```

## HTTP

```bash
auto-analyser serve   # http://127.0.0.1:8010
```

```bash
# Route an uploaded file (optional ?preset= and ?cascade= query params)
curl -F "file=@essay.docx" "http://127.0.0.1:8010/analyse"
curl -F "file=@essay.docx" "http://127.0.0.1:8010/analyse?preset=authentic-essay"

# List preset bundles
curl http://127.0.0.1:8010/presets
```
