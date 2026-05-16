from __future__ import annotations

import threading
import time

from . import autosync_manager, failure_detector


def start_background_scheduler(interval_secs: int = 30) -> None:
    def loop() -> None:
        while True:
            try:
                autosync_manager.run_once()
                failure_detector.run_once()
            except Exception:
                pass
            time.sleep(interval_secs)

    threading.Thread(target=loop, daemon=True).start()
