from __future__ import annotations

from . import storage


def evaluate_node(node: dict) -> str:
    if node["status"] == "stopped":
        return "container_stopped"
    if node["status"] == "failed":
        return "unknown"
    return "ok"


def run_once() -> None:
    for node in storage.list_nodes():
        state = evaluate_node(node)
        if node.get("failure_state") != state:
            storage.update_node(node["node_id"], failure_state=state)

