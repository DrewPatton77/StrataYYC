import pytest

from stratayyc import cli, steps
from stratayyc.config import ConfigError, Source, load_config

CONFIG = """
sources:
  a: {module: m, class: A, out_dir: raw/a, backfill: months}
  w: {module: m, class: W, out_dir: raw/w, backfill: years}
dbt: {project_dir: dbt, profiles_dir: dbt/.dbt}
export: {dir: exports}
"""


@pytest.fixture
def cfg_path(tmp_path):
    path = tmp_path / "pipeline.yml"
    path.write_text(CONFIG)
    return path


def test_load_config_resolves_paths(cfg_path):
    cfg = load_config(cfg_path)
    assert list(cfg.sources) == ["a", "w"]
    assert cfg.export_dir == cfg_path.parent / "exports"


def test_missing_key_names_the_key(tmp_path):
    bad = tmp_path / "pipeline.yml"
    bad.write_text(CONFIG.replace("module: m, ", "", 1))
    with pytest.raises(ConfigError, match=r"sources\.a: missing 'module'"):
        load_config(bad)


def test_run_goes_extract_upload_dbt_export_in_order(cfg_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        steps, "extract", lambda s, root, **k: calls.append(("extract", s.name))
    )
    monkeypatch.setattr(
        steps, "upload", lambda s, root: calls.append(("upload", s.name))
    )
    monkeypatch.setattr(steps, "run_dbt", lambda cfg, *a: calls.append(("dbt",)))
    monkeypatch.setattr(steps, "export", lambda cfg: calls.append(("export",)))
    assert cli.main(["--config", str(cfg_path), "run"]) == 0
    assert calls == [
        ("extract", "a"),
        ("upload", "a"),
        ("extract", "w"),
        ("upload", "w"),
        ("dbt",),
        ("export",),
    ]


def test_run_does_not_export_when_dbt_fails(cfg_path, monkeypatch):
    import subprocess

    def boom(cfg, *a):
        raise subprocess.CalledProcessError(1, "dbt")

    exported = []
    monkeypatch.setattr(steps, "extract", lambda *a, **k: None)
    monkeypatch.setattr(steps, "upload", lambda *a: None)
    monkeypatch.setattr(steps, "run_dbt", boom)
    monkeypatch.setattr(steps, "export", lambda cfg: exported.append(1))
    assert cli.main(["--config", str(cfg_path), "run"]) == 1
    assert exported == []


def test_unknown_source_is_a_config_error(cfg_path):
    assert cli.main(["--config", str(cfg_path), "extract", "nope"]) == 2


def test_backfill_passes_months_or_years(tmp_path, monkeypatch):
    seen = {}

    class Fake:
        def run(self, *args):
            seen["args"] = args

    monkeypatch.setattr(steps, "get_extractor", lambda s, root: Fake())
    steps.extract(
        Source("a", "m", "A", "raw/a", "months"),
        tmp_path,
        backfill=True,
        only=("2024-01",),
    )
    assert seen["args"] == (["2024-01"],)
    steps.extract(
        Source("w", "m", "W", "raw/w", "years"),
        tmp_path,
        backfill=True,
        only=("2020", "2022"),
    )
    assert seen["args"] == (2020, 2022)
