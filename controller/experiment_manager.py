from __future__ import annotations

import json
import uuid

from . import storage
from .models import ExperimentCreate


def list_experiments() -> list[dict]:
    return storage.list_experiments()


def create_experiment(payload: ExperimentCreate) -> dict:
    experiment_id = f"exp-{uuid.uuid4().hex[:12]}"
    return storage.insert_experiment(experiment_id, payload.name, payload.description, json.dumps(payload.labels, sort_keys=True))

