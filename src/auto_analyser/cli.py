"""auto-analyser CLI — file analysis router.

Usage:
  auto-analyser report.pdf
  auto-analyser data.csv --analyser records-analyser
  auto-analyser recording.mp3 --json
  auto-analyser detect notebook.ipynb
  auto-analyser status
  auto-analyser serve
  auto-analyser manifest
"""

import json
import sys
from pathlib import Path


def main() -> None:
    import argparse

    from lens_contract import run_contract_subcommands

    from .manifest import MANIFEST

    # `serve` and `manifest` are the family's shared subcommands (lens-contract).
    if run_contract_subcommands(
        MANIFEST,
        app_path="auto_analyser.api:app",
        default_port=8010,
        env_prefix="AUTO_ANALYSER",
    ):
        return

    argv = sys.argv[1:]

    # Orchestrator-specific subcommands.
    if argv and argv[0] == "detect":
        p = argparse.ArgumentParser(prog="auto-analyser detect")
        p.add_argument("file", type=Path, help="File to inspect")
        _cmd_detect(p.parse_args(argv[1:]))
        return
    if argv and argv[0] == "status":
        _cmd_status()
        return

    # Default command: analyse (bare positional). Also accept an explicit leading
    # `analyse` token — bundle-analyser invokes `auto-analyser analyse <file> --json`.
    if argv and argv[0] == "analyse":
        argv = argv[1:]

    parser = argparse.ArgumentParser(
        prog="auto-analyser",
        description="Route a file to the right analyser and return its analysis",
        epilog="subcommands: `serve`, `manifest`, `detect`, `status`",
    )
    parser.add_argument("file", type=Path, help="File to analyse")
    parser.add_argument("--analyser", help="Force a specific analyser (e.g. code-analyser)")
    parser.add_argument(
        "--no-cascade",
        dest="cascade",
        action="store_false",
        help="Disable cascade routing (e.g. image-analyser → diagram-analyser when is_diagram=True)",
    )
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output raw JSON")
    _cmd_analyse(parser.parse_args(argv))


def _cmd_analyse(args) -> None:
    from .router import Router, RoutingError

    router = Router()

    try:
        result = router.route(args.file, analyser_name=args.analyser, cascade=args.cascade)
    except RoutingError as e:
        if args.as_json:
            print(json.dumps({"error": str(e)}, indent=2, default=str), file=sys.stderr)
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.as_json:
        print(json.dumps(result, indent=2, default=str))
        return

    if result.get("warning"):
        print(f"Note: {result['warning']}\n")

    print(f"Routed to:  {result.get('routed_to', 'unknown')}")
    if "cascade" in result:
        casc = result["cascade"]
        if "error" in casc:
            print(f"Cascade:    {casc['routed_to']} (triggered by {casc.get('triggered_by','?')}) — failed: {casc['error']}")
        else:
            print(f"Cascade:    {casc['routed_to']} (triggered by {casc.get('triggered_by','?')})")
    print()
    print("Full result (use --json for machine-readable output):")
    _print_summary({k: v for k, v in result.items() if k not in ("routed_to", "warning", "cascade")})


def _cmd_detect(args) -> None:
    from .detector import detect

    result = detect(args.file)
    if result.warning:
        print(f"Note: {result.warning}")
    if result.analyser:
        print(f"{args.file.name} -> {result.analyser}")
    else:
        print(f"{args.file.name} -> unknown (no analyser configured for {result.extension})")
        sys.exit(1)


def _cmd_status() -> None:
    from .config import load_config
    import httpx

    config = load_config()
    print("Configured analysers:\n")

    for name, cfg in config.analysers.items():
        if cfg.type == "http":
            try:
                httpx.get(f"{cfg.url}/health", timeout=3).raise_for_status()
                status = "reachable"
            except Exception:
                status = "not reachable"
            print(f"  {name:<22} http  {cfg.url}  {status}")
        else:
            import subprocess
            try:
                subprocess.run([cfg.command, "--version"], capture_output=True, timeout=5)
                status = "installed"
            except FileNotFoundError:
                status = "not found"
            except subprocess.TimeoutExpired:
                status = "installed (timeout on --version)"
            print(f"  {name:<22} cli   {cfg.command}  {status}")


def _print_summary(data: dict) -> None:
    for key, value in data.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        elif isinstance(value, list):
            print(f"  {key}: [{len(value)} items]")
        else:
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
