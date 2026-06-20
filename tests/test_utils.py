import pytest

from src.utils import ConfigError, parse_args


def test_parse_args_league_and_day_range():
    args = parse_args(["NBA", "0", "1"])
    assert args.league == "NBA"
    assert args.start_day == 0
    assert args.end_day == 1


def test_parse_args_dry_run_flag():
    args = parse_args(["NBA", "0", "1", "--dry-run"])
    assert args.dry_run is True


def test_parse_args_dry_run_from_env(monkeypatch):
    monkeypatch.setenv("SLEEPER_DRY_RUN", "true")
    args = parse_args(["NBA", "0", "1"])
    assert args.dry_run is True


def test_get_args_unknown_league(monkeypatch):
    import src.utils as utils

    class FakeArgs:
        league = "NOPE"
        start_day = 0
        end_day = 0
        dry_run = True
        from_file = False
        live = False

    monkeypatch.setattr(utils, "parse_args", lambda argv=None: FakeArgs())

    with pytest.raises(ConfigError, match="Unknown league/stat"):
        utils.getArgs()
