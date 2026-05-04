"""poly-lens CLI — multi-lens analysis router.

Usage:
  poly-lens analyse report.pdf
  poly-lens analyse data.csv --lens data-lens
  poly-lens analyse recording.mp3 --json
  poly-lens detect notebook.ipynb
  poly-lens status
"""

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="poly-lens",
        description="Route files to the right analysis lens",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # poly-lens analyse
    analyse = sub.add_parser("analyse", help="Analyse a file")
    analyse.add_argument("file", type=Path, help="File to analyse")
    analyse.add_argument("--lens", help="Force a specific lens (e.g. document-lens)")
    analyse.add_argument("--json", action="store_true", dest="as_json",
                         help="Output raw JSON")

    # poly-lens detect
    detect_cmd = sub.add_parser("detect", help="Show which lens would handle a file")
    detect_cmd.add_argument("file", type=Path)

    # poly-lens status
    sub.add_parser("status", help="Show configured lenses and whether they are reachable")

    args = parser.parse_args()

    if args.command == "analyse":
        _cmd_analyse(args)
    elif args.command == "detect":
        _cmd_detect(args)
    elif args.command == "status":
        _cmd_status()


def _cmd_analyse(args) -> None:
    from .router import Router, RoutingError

    router = Router()

    try:
        result = router.route(args.file, lens_name=args.lens)
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
    print()
    print("Full result (use --json for machine-readable output):")
    _print_summary({k: v for k, v in result.items() if k not in ("routed_to", "warning")})


def _cmd_detect(args) -> None:
    from .detector import detect

    result = detect(args.file)
    if result.warning:
        print(f"Note: {result.warning}")
    if result.lens:
        print(f"{args.file.name} -> {result.lens}")
    else:
        print(f"{args.file.name} -> unknown (no lens configured for {result.extension})")
        sys.exit(1)


def _cmd_status() -> None:
    from .config import load_config
    import httpx

    config = load_config()
    print("Configured lenses:\n")

    for name, lens in config.lenses.items():
        if lens.type == "http":
            try:
                httpx.get(f"{lens.url}/health", timeout=3).raise_for_status()
                status = "reachable"
            except Exception:
                status = "not reachable"
            print(f"  {name:<20} http  {lens.url}  {status}")
        else:
            try:
                subprocess.run(
                    [lens.command, "--version"],
                    capture_output=True, timeout=5
                )
                status = "installed"
            except FileNotFoundError:
                status = "not found"
            except subprocess.TimeoutExpired:
                status = "installed (timeout on --version)"
            print(f"  {name:<20} cli   {lens.command}  {status}")


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
