from __future__ import annotations

import os
from datetime import datetime, timezone

from . import storage
from .runtime_probe import collect_node_observation, rpc


DEFAULT_SYNC_COMPLETE_LAG = 2
DEFAULT_COMPLETION_OBSERVATIONS = 3


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
    sync_run_id = node.get("sync_run_id")
    gw_height = gateway_height()
    if not sync_run_id or gw_height is None or gw_height <= 0:
        return False
    if not recent_heights_match_gateway(node, sync_run_id, gw_height):
        return False
    return chain_validation_passed(node)


def chain_validation_passed(node: dict) -> bool:
    if os.environ.get("RUNTIME_REQUIRE_VALIDATE_CHAIN", "true").lower() in ("0", "false", "no"):
        return True
    try:
        rpc(node, "validate_chain")
    except Exception:
        return False
    return True


def sync_complete_lag() -> int:
    raw_value = os.environ.get("RUNTIME_SYNC_COMPLETE_LAG", str(DEFAULT_SYNC_COMPLETE_LAG))
    try:
        value = int(raw_value)
    except ValueError:
        return DEFAULT_SYNC_COMPLETE_LAG
    if value < 0:
        return DEFAULT_SYNC_COMPLETE_LAG
    return value


def completion_observations() -> int:
    raw_value = os.environ.get("RUNTIME_SYNC_COMPLETE_OBSERVATIONS", str(DEFAULT_COMPLETION_OBSERVATIONS))
    try:
        value = int(raw_value)
    except ValueError:
        return DEFAULT_COMPLETION_OBSERVATIONS
    return max(1, value)


def recent_heights_match_gateway(node: dict, sync_run_id: str, gw_height: int) -> bool:
    required = completion_observations()
    scan_limit = max(required * 4, required)
    observations = [
        item
        for item in storage.recent_observations(node["node_id"], scan_limit)
        if item.get("sync_run_id") == sync_run_id
    ][:required]
    if len(observations) < required:
        return False
    allowed_lag = sync_complete_lag()
    for item in observations:
        if not item.get("api_up") or not item.get("container_running"):
            return False
        if (item.get("peer_count") or 0) <= 0 or item.get("height") is None:
            return False
        if abs(int(gw_height) - int(item["height"])) > allowed_lag:
            return False
    return True


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
