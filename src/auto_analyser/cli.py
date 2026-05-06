"""auto-analyser CLI — file analysis router.

Usage:
  auto-analyser report.pdf
  auto-analyser data.csv --analyser records-analyser
  auto-analyser recording.mp3 --json
  auto-analyser detect notebook.ipynb
  auto-analyser status
"""

import json
import sys
from pathlib import Path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="auto-analyser",
        description="Route files to the right analyser",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    analyse = sub.add_parser("analyse", help="Analyse a file")
    analyse.add_argument("file", type=Path, help="File to analyse")
    analyse.add_argument("--analyser", help="Force a specific analyser (e.g. code-analyser)")
    analyse.add_argument("--json", action="store_true", dest="as_json", help="Output raw JSON")

    detect_cmd = sub.add_parser("detect", help="Show which analyser would handle a file")
    detect_cmd.add_argument("file", type=Path)

    sub.add_parser("status", help="Show configured analysers and whether they are reachable")

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
        result = router.route(args.file, analyser_name=args.analyser)
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
