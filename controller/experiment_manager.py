from __future__ import annotations

import json
import uuid

from fastapi import HTTPException

from . import storage
from .models import ExperimentCreate, NodeCreate


def list_experiments() -> list[dict]:
    return storage.list_experiments()


def create_experiment(payload: ExperimentCreate) -> dict:
    experiment_id = f"exp-{uuid.uuid4().hex[:12]}"
    return storage.insert_experiment(
        experiment_id,
        payload.name,
        payload.description,
        json.dumps(payload.labels, sort_keys=True),
        json.dumps(payload.node_profiles, sort_keys=True),
    )


def start_experiment(experiment_id: str) -> dict:
    experiment = storage.get_experiment(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    from . import node_manager

    created = []
    profiles = json.loads(experiment.get("node_profiles_json") or "[]")
    for item in profiles:
        node_type = item.get("node_type", "grin-rust")
        profile = item.get("profile", "default")
        count = int(item.get("count", item.get("nodes", 1)))
        autosync_enabled = item.get("autosync_enabled")
        if node_type not in ("grin-rust", "grinpp"):
            raise HTTPException(status_code=400, detail=f"invalid experiment node_type: {node_type}")
        for _index in range(max(0, min(count, 50))):
            created.append(
                node_manager.create_node(
                    NodeCreate(
                        node_type=node_type,
                        profile=profile,
                        experiment_id=experiment_id,
                        autosync_enabled=autosync_enabled,
                    )
                )
            )
    updated = storage.update_experiment(experiment_id, status="running", started_at=storage.utcnow_iso())
    return {"experiment": updated, "created_nodes": created}


def stop_experiment(experiment_id: str) -> dict:
    experiment = storage.get_experiment(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    from . import node_manager

    stopped = []
    for node in storage.list_nodes_for_experiment(experiment_id):
        stopped.append(node_manager.stop_node(node["node_id"]))
    updated = storage.update_experiment(experiment_id, status="stopped", stopped_at=storage.utcnow_iso())
    return {"experiment": updated, "stopped_nodes": stopped}
