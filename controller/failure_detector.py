from __future__ import annotations

from . import storage


def evaluate_node(node: dict, observations: list[dict] | None = None) -> str:
    if node["status"] == "stopped":
        return "container_stopped"
    if node["status"] == "failed":
        return "container_stopped"
    observations = observations or []
    latest = observations[0] if observations else storage.latest_observation(node["node_id"])
    if not latest:
        return "unknown"
    if not latest.get("container_running"):
        return "container_stopped"
    if not latest.get("api_up"):
        return "api_unreachable"
    if latest.get("peer_count") == 0 and len(observations) >= 3 and all((item.get("peer_count") or 0) == 0 for item in observations[:3]):
        return "peerless"
    heights = [item.get("height") for item in observations[:6] if item.get("height") is not None]
    states = {item.get("sync_state") for item in observations[:6]}
    if len(heights) >= 6 and max(heights) == min(heights) and states.isdisjoint({"no_sync", "synced", "sync_finished"}):
        return "stuck"
    if latest.get("cpu_percent") is not None and float(latest["cpu_percent"]) > 95:
        return "resource_limit"
    if latest.get("ram_bytes") is not None and int(latest["ram_bytes"]) > 14 * 1024 * 1024 * 1024:
        return "resource_limit"
    return "ok"


def run_once() -> None:
    for node in storage.list_nodes():
        state = evaluate_node(node, storage.recent_observations(node["node_id"], 6))
        if node.get("failure_state") != state:
            storage.update_node(node["node_id"], failure_state=state)
