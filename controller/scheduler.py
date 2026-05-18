from __future__ import annotations

import threading
import time

from . import autosync_manager, failure_detector


DEFAULT_INTERVAL_SECS = 10


def _run_scheduler_loop(
    interval_secs: int = DEFAULT_INTERVAL_SECS,
    iterations: int | None = None,
    sleep_fn=time.sleep,
    monotonic_fn=time.monotonic,
) -> None:
    interval_secs = max(1, int(interval_secs))
    next_run = monotonic_fn()
    count = 0
    while iterations is None or count < iterations:
        try:
            autosync_manager.run_once()
            failure_detector.run_once()
        except Exception:
            pass

        count += 1
        next_run += interval_secs
        delay = next_run - monotonic_fn()
        if delay > 0:
            sleep_fn(delay)
        else:
            next_run = monotonic_fn()


def start_background_scheduler(interval_secs: int = DEFAULT_INTERVAL_SECS) -> None:
    def loop() -> None:
        _run_scheduler_loop(interval_secs)

    threading.Thread(target=loop, daemon=True).start()
