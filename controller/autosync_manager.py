from __future__ import annotations

from datetime import datetime, timezone

from . import storage
from .runtime_probe import collect_node_observation


FULL_SYNC_STATES = {"synced", "sync_finished"}
IN_PROGRESS_STATES = {
    "awaiting_peers",
    "header_sync",
    "body_sync",
    "txhashset_download",
    "txhashset_setup",
    "txhashset_rangeproofs_validation",
    "txhashset_kernels_validation",
    "txhashset_save",
    "txhashset_pibd",
    "starting",
    "reset",
    "created",
}


def should_reset_after_sync(node: dict, latest_sync_state: str, observation: dict | None = None) -> bool:
    return bool(node.get("autosync_enabled")) and is_sync_complete(node, latest_sync_state, observation or {})


def gateway_height() -> int | None:
    latest = storage.latest_observation("gw")
    if not latest:
        return None
    height = latest.get("height")
    return int(height) if height is not None else None


def is_sync_complete(node: dict, latest_sync_state: str, observation: dict) -> bool:
    if node.get("node_type") == "gateway":
        return False
    if not observation.get("api_up") or not observation.get("container_running"):
        return False
    if (observation.get("peer_count") or 0) <= 0:
        return False
    if latest_sync_state in FULL_SYNC_STATES:
        return True
    height = observation.get("height")
    gw_height = gateway_height()
    if height is None or gw_height is None or gw_height <= 0:
        return False
    lag = int(gw_height) - int(height)
    allowed_lag = int(__import__("os").environ.get("RUNTIME_SYNC_COMPLETE_LAG", "2"))
    return lag >= 0 and lag <= allowed_lag


def set_autosync(node_id: str, enabled: bool) -> dict:
    return storage.update_node(node_id, autosync_enabled=enabled, last_action="autosync_enable" if enabled else "autosync_disable")


def observe_node(node: dict) -> dict:
    observation = collect_node_observation(node)
    observation["sync_run_id"] = node.get("sync_run_id")
    storage.insert_observation(node["node_id"], observation)
    updates = {
        "sync_state": observation.get("sync_state") or node.get("sync_state") or "unknown",
    }
    if observation.get("container_running"):
        updates["status"] = "running"
    elif node["status"] == "running":
        updates["status"] = "failed"
    storage.update_node(node["node_id"], **updates)
    return observation


def handle_sync_completion(node: dict, observation: dict) -> None:
    latest_state = observation.get("sync_state") or "unknown"
    previous_state = node.get("sync_state") or "unknown"
    height = observation.get("height")
    sync_run_id = node.get("sync_run_id")
    completed = is_sync_complete(node, latest_state, observation) and bool(sync_run_id)
    if not completed:
        return
    if sync_run_id:
        storage.complete_benchmark_run(node, sync_run_id, height, result="success")
    storage.update_node(
        node["node_id"],
        last_sync_completed_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        sync_state=latest_state,
        last_action="sync-completed",
    )
    if should_reset_after_sync(node, latest_state, observation):
        from . import node_manager

        storage.log_action("autosync-reset", node["node_id"], f"completed {sync_run_id}")
        node_manager.reset_chain(node["node_id"])


def run_once() -> None:
    for node in storage.list_nodes():
        if node["status"] == "deleted":
            continue
        observation = observe_node(node)
        if node["node_type"] != "gateway":
            handle_sync_completion(node, observation)
