"""Command line entry point: `uv run stratayyc <command>`. See `--help`."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from stratayyc import steps
from stratayyc.config import Config, ConfigError, load_config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stratayyc", description="Calgary 311 and weather pipeline"
    )
    p.add_argument(
        "--config",
        default="pipeline.yml",
        help="pipeline config (default: ./pipeline.yml)",
    )
    p.add_argument(
        "--root",
        help="where raw files are written (default: the folder holding the config)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser(
        "extract", help="fetch from the APIs (daily incremental, or --backfill)"
    )
    e.add_argument("sources", nargs="*", help="source names (default: all)")
    e.add_argument(
        "--backfill",
        action="store_true",
        help="run the full history instead of the incremental",
    )
    e.add_argument(
        "--only",
        nargs="+",
        default=[],
        help="months (YYYY-MM) or START [END] years; one source only",
    )

    u = sub.add_parser("upload", help="copy raw files to S3")
    u.add_argument("sources", nargs="*", help="source names (default: all)")

    d = sub.add_parser("dbt", help="run dbt (default: build)")
    d.add_argument(
        "dbt_args",
        nargs=argparse.REMAINDER,
        help="passed to dbt, e.g. --select fct_service_requests",
    )

    sub.add_parser("export", help="write the dashboard tables to CSV and S3")
    sub.add_parser(
        "run", help="extract + upload every source, then dbt build, then export"
    )
    return p


def _pick(cfg: Config, names: list[str]):
    unknown = [n for n in names if n not in cfg.sources]
    if unknown:
        raise ConfigError(
            f"unknown source {unknown}; choose from {sorted(cfg.sources)}"
        )
    return [cfg.sources[n] for n in (names or cfg.sources)]


def dispatch(args: argparse.Namespace, cfg: Config) -> None:
    root = Path(args.root) if args.root else cfg.base_dir
    if args.command == "extract":
        chosen = _pick(cfg, args.sources)
        if args.only and len(chosen) != 1:
            raise ConfigError("--only needs exactly one source")
        for s in chosen:
            steps.extract(s, root, backfill=args.backfill, only=tuple(args.only))
    elif args.command == "upload":
        for s in _pick(cfg, args.sources):
            steps.upload(s, root)
    elif args.command == "dbt":
        extra = list(args.dbt_args)
        command = extra.pop(0) if extra and not extra[0].startswith("-") else "build"
        steps.run_dbt(cfg, command, tuple(extra))
    elif args.command == "export":
        steps.export(cfg)
    elif args.command == "run":
        for s in cfg.sources.values():
            steps.extract(s, root)
            steps.upload(s, root)
        steps.run_dbt(cfg)  # a failed test stops here, so a bad build is never exported
        steps.export(cfg)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        dispatch(args, load_config(args.config))
    except ConfigError as err:
        print(f"config error: {err}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as err:
        print(f"dbt failed with exit code {err.returncode}", file=sys.stderr)
        return err.returncode
    except KeyError as err:
        print(f"missing environment variable: {err}", file=sys.stderr)
        return 1
    return 0
