from __future__ import annotations

import os

from . import storage


DEFAULT_FAILURE_CONFIRMATION_OBSERVATIONS = 3
DEFAULT_STUCK_CONFIRMATION_OBSERVATIONS = 12


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


def benchmark_failure_confirmed(state: str, observations: list[dict]) -> bool:
    if state in ("ok", "unknown"):
        return False
    required = failure_confirmation_observations()
    if len(observations) < required:
        return False
    recent = observations[:required]
    if state == "api_unreachable":
        return all(item.get("container_running") and not item.get("api_up") for item in recent)
    if state == "container_stopped":
        return all(not item.get("container_running") for item in recent)
    if state == "peerless":
        return all(item.get("container_running") and item.get("api_up") and (item.get("peer_count") or 0) == 0 for item in recent)
    if state == "stuck":
        return stuck_failure_confirmed(observations)
    return False


def stuck_failure_confirmed(observations: list[dict]) -> bool:
    required = stuck_confirmation_observations()
    if len(observations) < required:
        return False
    recent = observations[:required]
    heights = [item.get("height") for item in recent if item.get("height") is not None]
    header_heights = [item.get("header_height") for item in recent if item.get("header_height") is not None]
    if len(heights) < required or max(heights) != min(heights):
        return False
    if len(header_heights) == required and max(header_heights) != min(header_heights):
        return False
    return all(item.get("container_running") and item.get("api_up") for item in recent)


def failure_confirmation_observations() -> int:
    raw_value = os.environ.get("RUNTIME_BENCHMARK_FAILURE_OBSERVATIONS", str(DEFAULT_FAILURE_CONFIRMATION_OBSERVATIONS))
    try:
        value = int(raw_value)
    except ValueError:
        return DEFAULT_FAILURE_CONFIRMATION_OBSERVATIONS
    return max(1, value)


def stuck_confirmation_observations() -> int:
    raw_value = os.environ.get("RUNTIME_STUCK_FAILURE_OBSERVATIONS", str(DEFAULT_STUCK_CONFIRMATION_OBSERVATIONS))
    try:
        value = int(raw_value)
    except ValueError:
        return DEFAULT_STUCK_CONFIRMATION_OBSERVATIONS
    return max(failure_confirmation_observations(), value)


def observations_for_sync_run(observations: list[dict], sync_run_id: str | None) -> list[dict]:
    if not sync_run_id:
        return []
    return [item for item in observations if item.get("sync_run_id") == sync_run_id]


def run_once() -> None:
    for node in storage.list_nodes():
        observations = storage.recent_observations(node["node_id"], max(12, stuck_confirmation_observations()))
        state = evaluate_node(node, observations)
        if node.get("failure_state") != state:
            storage.update_node(node["node_id"], failure_state=state)
        run = storage.get_benchmark_run(node["node_id"], node["sync_run_id"]) if node.get("sync_run_id") else None
        run_observations = observations_for_sync_run(observations, node.get("sync_run_id"))
        benchmark_state = evaluate_node(node, run_observations) if run_observations else "unknown"
        if benchmark_failure_confirmed(benchmark_state, run_observations) and run and run.get("result") == "running" and node.get("node_type") != "gateway":
            latest = run_observations[0] if run_observations else storage.latest_observation(node["node_id"]) or {}
            storage.complete_benchmark_run(
                node,
                node["sync_run_id"],
                latest.get("height"),
                result="failed",
                error_message=benchmark_state,
            )
