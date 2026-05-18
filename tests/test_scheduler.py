from controller import scheduler


def test_scheduler_uses_fixed_cadence(monkeypatch):
    now = {"value": 0.0}
    sleeps = []

    def monotonic():
        return now["value"]

    def sleep(seconds):
        sleeps.append(seconds)
        now["value"] += seconds

    def autosync_run_once():
        now["value"] += 5

    def failure_run_once():
        now["value"] += 4

    monkeypatch.setattr(scheduler.autosync_manager, "run_once", autosync_run_once)
    monkeypatch.setattr(scheduler.failure_detector, "run_once", failure_run_once)

    scheduler._run_scheduler_loop(30, iterations=1, sleep_fn=sleep, monotonic_fn=monotonic)

    assert sleeps == [21]


def test_scheduler_does_not_try_to_catch_up_when_run_exceeds_interval(monkeypatch):
    now = {"value": 0.0}
    sleeps = []

    def monotonic():
        return now["value"]

    def sleep(seconds):
        sleeps.append(seconds)
        now["value"] += seconds

    def autosync_run_once():
        now["value"] += 8

    def failure_run_once():
        now["value"] += 8

    monkeypatch.setattr(scheduler.autosync_manager, "run_once", autosync_run_once)
    monkeypatch.setattr(scheduler.failure_detector, "run_once", failure_run_once)

    scheduler._run_scheduler_loop(10, iterations=1, sleep_fn=sleep, monotonic_fn=monotonic)

    assert sleeps == []
