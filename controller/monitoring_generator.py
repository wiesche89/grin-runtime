from __future__ import annotations

from .utils import PROM_TARGETS_DIR, write_json_if_changed


def generate(nodes: list[dict]) -> None:
    active = [node for node in nodes if node["status"] != "deleted"]
    grin_nodes = []
    for node in active:
        grin_nodes.append(
            {
                "targets": ["grin-exporter:9108"],
                "labels": {
                    "node_id": node["node_id"],
                    "node_name": node["node_name"],
                    "node_type": node["node_type"],
                    "profile": node["profile"],
                    "experiment_id": node.get("experiment_id") or "",
                    "image_tag": node.get("image_tag") or "",
                    "commit_hash": node.get("git_commit_hash") or "",
                },
            }
        )
    write_json_if_changed(PROM_TARGETS_DIR / "grin-nodes.json", grin_nodes)

