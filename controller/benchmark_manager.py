from __future__ import annotations

from . import storage


def list_benchmarks() -> list[dict]:
    return storage.list_benchmarks()

