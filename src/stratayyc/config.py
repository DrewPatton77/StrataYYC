"""Load and check pipeline.yml. Errors name the key that is wrong, so a typo is easy to find."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

BACKFILL_KINDS = ("months", "years")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Source:
    name: str
    module: str
    class_name: str
    out_dir: str
    backfill: str


@dataclass(frozen=True)
class Config:
    base_dir: Path
    sources: dict[str, Source]
    dbt_project_dir: Path
    dbt_profiles_dir: Path
    export_dir: Path


def _need(block: object, key: str, where: str):
    if not isinstance(block, dict) or key not in block:
        raise ConfigError(f"{where}: missing '{key}'")
    return block[key]


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    raw = yaml.safe_load(path.read_text()) or {}
    base = path.resolve().parent

    raw_sources = _need(raw, "sources", "config")
    if not isinstance(raw_sources, dict) or not raw_sources:
        raise ConfigError("config: 'sources' must list at least one source")
    sources = {}
    for name, block in raw_sources.items():
        where = f"sources.{name}"
        backfill = block.get("backfill", "months") if isinstance(block, dict) else None
        if backfill not in BACKFILL_KINDS:
            raise ConfigError(f"{where}: 'backfill' must be one of {BACKFILL_KINDS}")
        sources[name] = Source(
            name=name,
            module=_need(block, "module", where),
            class_name=_need(block, "class", where),
            out_dir=_need(block, "out_dir", where),
            backfill=backfill,
        )

    dbt = _need(raw, "dbt", "config")
    export = _need(raw, "export", "config")
    return Config(
        base_dir=base,
        sources=sources,
        dbt_project_dir=base / _need(dbt, "project_dir", "dbt"),
        dbt_profiles_dir=base / _need(dbt, "profiles_dir", "dbt"),
        export_dir=base / _need(export, "dir", "export"),
    )
