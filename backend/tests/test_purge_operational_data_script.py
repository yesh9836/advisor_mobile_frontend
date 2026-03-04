import json
from types import SimpleNamespace


def test_purge_operational_data_script_runs_one_shot_by_default(monkeypatch, capsys):
    from scripts import purge_operational_data as script

    monkeypatch.setattr(
        script,
        "_parse_args",
        lambda: SimpleNamespace(
            interval_seconds=0.0,
            max_cycles=1,
            log_level="INFO",
        ),
    )
    monkeypatch.setattr(
        script,
        "_purge_once",
        lambda: {"batch_size": 500, "total_deleted": 7},
    )

    exit_code = script.main()

    assert exit_code == 0
    stdout = capsys.readouterr().out.strip()
    assert json.loads(stdout) == {"batch_size": 500, "total_deleted": 7}


def test_purge_operational_data_script_one_shot_returns_failure_on_exception(monkeypatch):
    from scripts import purge_operational_data as script

    captured = []
    monkeypatch.setattr(
        script,
        "_parse_args",
        lambda: SimpleNamespace(
            interval_seconds=0.0,
            max_cycles=1,
            log_level="INFO",
        ),
    )

    def _raise():
        raise RuntimeError("forced retention failure")

    monkeypatch.setattr(script, "_purge_once", _raise)
    monkeypatch.setattr(
        script,
        "capture_exception",
        lambda exc, tags=None, context=None: captured.append(
            {"exc": str(exc), "tags": tags or {}, "context": context}
        ),
    )

    exit_code = script.main()

    assert exit_code == 1
    assert len(captured) == 1
    assert captured[0]["tags"]["operation"] == "one_shot_purge"


def test_purge_operational_data_script_continuous_mode_runs_max_cycles(monkeypatch):
    from scripts import purge_operational_data as script

    cycles = {"count": 0}
    sleep_calls = []

    monkeypatch.setattr(
        script,
        "_parse_args",
        lambda: SimpleNamespace(
            interval_seconds=15.0,
            max_cycles=2,
            log_level="INFO",
        ),
    )
    monkeypatch.setattr(
        script,
        "_purge_once",
        lambda: cycles.__setitem__("count", cycles["count"] + 1)
        or {"batch_size": 500, "total_deleted": cycles["count"]},
    )
    monkeypatch.setattr(script.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    exit_code = script.main()

    assert exit_code == 0
    assert cycles["count"] == 2
    assert sleep_calls == [15.0]


def test_purge_operational_data_script_continuous_mode_continues_after_cycle_failure(monkeypatch):
    from scripts import purge_operational_data as script

    attempts = {"count": 0}
    sleep_calls = []
    captured = []

    monkeypatch.setattr(
        script,
        "_parse_args",
        lambda: SimpleNamespace(
            interval_seconds=30.0,
            max_cycles=2,
            log_level="INFO",
        ),
    )

    def _purge_once():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("transient purge failure")
        return {"batch_size": 500, "total_deleted": 3}

    monkeypatch.setattr(script, "_purge_once", _purge_once)
    monkeypatch.setattr(script.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(
        script,
        "capture_exception",
        lambda exc, tags=None, context=None: captured.append(
            {"exc": str(exc), "tags": tags or {}, "context": context}
        ),
    )

    exit_code = script.main()

    assert exit_code == 0
    assert attempts["count"] == 2
    assert sleep_calls == [30.0]
    assert len(captured) == 1
    assert captured[0]["tags"]["operation"] == "loop_purge"
