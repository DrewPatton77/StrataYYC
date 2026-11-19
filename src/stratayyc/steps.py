"""The pipeline steps. Each one is a plain function, so the CLI (and later the DAG) call the same code."""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from stratayyc.config import Config, Source


def _include_on_path() -> None:
    """The extractors live in include/, which is not part of the installed package."""
    include = os.environ.get("STRATAYYC_INCLUDE") or str(
        Path(__file__).resolve().parents[2] / "include"
    )
    if include not in sys.path:
        sys.path.insert(0, include)


def get_extractor(source: Source, root: Path):
    _include_on_path()
    cls = getattr(importlib.import_module(source.module), source.class_name)
    return cls(out_dir=Path(root) / source.out_dir)


def extract(
    source: Source, root: Path, backfill: bool = False, only: tuple[str, ...] = ()
) -> None:
    """Daily incremental by default. With backfill=True, run the full history (or just `only`)."""
    extractor = get_extractor(source, root)
    if not backfill:
        extractor.run_incremental(strict=True)  # a count mismatch fails the step
    elif source.backfill == "months":
        extractor.run(list(only) or None)
    else:  # years: --only START [END]
        years = [int(y) for y in only]
        if len(years) > 2:
            raise ValueError("--only takes a start year and an optional end year")
        extractor.run(*years)


def upload(source: Source, root: Path) -> int:
    return get_extractor(source, root).upload_to_s3(bucket=os.environ["S3_BUCKET"])


def run_dbt(cfg: Config, command: str = "build", extra: tuple[str, ...] = ()) -> None:
    """dbt uses its own IAM user, so DBT_AWS_* is renamed to AWS_* for this one command.
    STRATAYYC_DBT points at the dbt executable when it is not on PATH (the Airflow image keeps it in a venv)."""
    exe = os.environ.get("STRATAYYC_DBT") or shutil.which("dbt")
    if exe is None:
        raise RuntimeError(
            "dbt not found. Run through uv: 'uv run stratayyc dbt', or set STRATAYYC_DBT"
        )
    env = dict(os.environ)
    for suffix in ("ACCESS_KEY_ID", "SECRET_ACCESS_KEY"):
        if os.environ.get(f"DBT_AWS_{suffix}"):
            env[f"AWS_{suffix}"] = os.environ[f"DBT_AWS_{suffix}"]
    cmd = [
        exe,
        command,
        "--project-dir",
        str(cfg.dbt_project_dir),
        "--profiles-dir",
        str(cfg.dbt_profiles_dir),
        *extra,
    ]
    subprocess.run(cmd, check=True, env=env)


def export(cfg: Config) -> dict:
    _include_on_path()
    from export_marts import EXPORT_TABLES, export_tables

    return export_tables(
        EXPORT_TABLES, str(cfg.export_dir), bucket=os.environ["S3_BUCKET"]
    )
