from types import SimpleNamespace


def test_run_stripe_webhook_pipeline_runs_cleanup_in_same_loop(monkeypatch):
    from scripts import run_stripe_webhook_pipeline as pipeline_script

    calls = []
    monotonic_values = iter([100.0, 100.0])

    monkeypatch.setattr(
        pipeline_script,
        "_parse_args",
        lambda: SimpleNamespace(
            poll_interval_seconds=0.1,
            reconcile_interval_seconds=60.0,
            cleanup_interval_seconds=15.0,
            max_cycles=1,
            log_level="INFO",
        ),
    )
    monkeypatch.setattr(pipeline_script.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(pipeline_script, "_run_reconciliation_once", lambda: calls.append("reconcile") or {})
    monkeypatch.setattr(
        pipeline_script,
        "_process_inbox_batch_with_heartbeat",
        lambda: calls.append("inbox")
        or {"selected": 0, "processed": 0, "retried": 0, "failed": 0, "non_retryable": 0},
    )
    monkeypatch.setattr(
        pipeline_script,
        "process_cleanup_batch_with_heartbeat",
        lambda: calls.append("cleanup") or {"selected": 0, "processed": 0, "retried": 0, "failed": 0},
    )

    exit_code = pipeline_script.main()

    assert exit_code == 0
    assert calls == ["reconcile", "inbox", "cleanup"]


def test_run_stripe_webhook_pipeline_continues_after_cleanup_failure(monkeypatch):
    from scripts import run_stripe_webhook_pipeline as pipeline_script

    counters = {"inbox": 0, "cleanup": 0}
    captured = []
    monotonic_values = iter([0.0, 0.0, 1.0, 1.0])

    monkeypatch.setattr(
        pipeline_script,
        "_parse_args",
        lambda: SimpleNamespace(
            poll_interval_seconds=0.1,
            reconcile_interval_seconds=60.0,
            cleanup_interval_seconds=0.5,
            max_cycles=2,
            log_level="INFO",
        ),
    )
    monkeypatch.setattr(pipeline_script.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(pipeline_script, "_run_reconciliation_once", lambda: {})
    monkeypatch.setattr(
        pipeline_script,
        "capture_exception",
        lambda exc, tags=None, context=None: captured.append(
            {"exc": str(exc), "tags": tags or {}, "context": context}
        ),
    )
    monkeypatch.setattr(
        pipeline_script,
        "_process_inbox_batch_with_heartbeat",
        lambda: counters.__setitem__("inbox", counters["inbox"] + 1)
        or {"selected": 1, "processed": 1, "retried": 0, "failed": 0, "non_retryable": 0},
    )

    def _cleanup():
        counters["cleanup"] += 1
        if counters["cleanup"] == 1:
            raise RuntimeError("forced cleanup failure")
        return {"selected": 1, "processed": 1, "retried": 0, "failed": 0}

    monkeypatch.setattr(pipeline_script, "process_cleanup_batch_with_heartbeat", _cleanup)

    exit_code = pipeline_script.main()

    assert exit_code == 0
    assert counters["inbox"] == 2
    assert counters["cleanup"] == 2
    assert len(captured) == 1
    assert captured[0]["tags"]["operation"] == "cleanup_batch"
