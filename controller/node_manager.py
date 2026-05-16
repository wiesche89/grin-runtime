from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException

from . import compose_generator, config_generator, monitoring_generator, storage
from .models import NodeCreate
from .security import ensure_child_path, validate_node_id
from .utils import NODES_DIR, REPO_ROOT, compose_args, remove_path, run_command, utcnow_iso


RUST_IMAGE = os.environ.get("GRIN_RUST_IMAGE", "grin-runtime")
RUST_TAG = os.environ.get("GRIN_RUST_TAG", "staging")
GRINPP_IMAGE = os.environ.get("GRINPP_IMAGE", "grin-runtime-grinpp")
GRINPP_TAG = os.environ.get("GRINPP_TAG", "master")


def refresh_generated_files() -> None:
    nodes = storage.list_nodes()
    compose_generator.generate(nodes)
    monitoring_generator.generate(nodes)


def next_node_number(prefix: str) -> int:
    used = set()
    for node in storage.list_nodes():
        node_id = node["node_id"]
        if node_id.startswith(prefix):
            try:
                used.add(int(node_id.removeprefix(prefix)))
            except ValueError:
                continue
    candidate = 1
    while candidate in used:
        candidate += 1
    return candidate


def allocate_identity(node_type: str) -> tuple[str, str]:
    if node_type == "grinpp":
        number = next_node_number("grinpp-node-")
        node_id = f"grinpp-node-{number}"
    else:
        number = next_node_number("node-")
        node_id = f"node-{number}"
    return node_id, node_id


def allocate_ports(node_id: str) -> tuple[int, int, int]:
    digits = "".join(ch for ch in node_id if ch.isdigit())
    offset = int(digits or "0")
    if node_id.startswith("grinpp"):
        offset += 500
    return 14000 + offset, 15000 + offset, 16000 + offset


def create_node(payload: NodeCreate) -> dict:
    profile_cfg = config_generator.profile_config(payload.profile)
    node_id, node_name = allocate_identity(payload.node_type)
    api_port, p2p_port, metrics_port = allocate_ports(node_id)
    if payload.node_type == "grinpp":
        node_dir, config_hash = config_generator.generate_grinpp_config(node_id, payload.profile)
        docker_image = GRINPP_IMAGE
        image_tag = payload.image_tag or GRINPP_TAG
    else:
        node_dir, config_hash = config_generator.generate_rust_config(node_id, payload.profile)
        docker_image = RUST_IMAGE
        image_tag = payload.image_tag or RUST_TAG
    now = utcnow_iso()
    record = {
        "node_id": node_id,
        "node_name": node_name,
        "node_type": payload.node_type,
        "profile": payload.profile,
        "experiment_id": payload.experiment_id,
        "container_name": node_name,
        "node_path": str(node_dir.relative_to(REPO_ROOT)).replace("\\", "/"),
        "api_port": api_port,
        "p2p_port": p2p_port,
        "metrics_port": metrics_port,
        "docker_image": docker_image,
        "image_tag": image_tag,
        "image_digest": None,
        "git_commit_hash": os.environ.get("GRIN_GIT_COMMIT"),
        "build_date": os.environ.get("GRIN_BUILD_DATE"),
        "runtime_config_hash": config_hash,
        "autosync_enabled": profile_cfg["autosync_default"] if payload.autosync_enabled is None else payload.autosync_enabled,
        "sync_state": "created",
        "failure_state": "unknown",
        "status": "created",
        "sync_run_id": None,
        "last_sync_completed_at": None,
        "created_at": now,
        "updated_at": now,
        "last_action": "create",
    }
    storage.insert_node(record)
    storage.log_action("create", node_id)
    refresh_generated_files()
    if payload.start:
        start_node(node_id)
    return storage.get_node(node_id)


def get_required_node(node_id: str) -> dict:
    validate_node_id(node_id)
    node = storage.get_node(node_id)
    if node is None or node["status"] == "deleted":
        raise HTTPException(status_code=404, detail="node not found")
    return node


def start_node(node_id: str, *, dry_run: bool = False) -> dict:
    node = get_required_node(node_id)
    if node["node_type"] == "gateway":
        service = "grin-gw"
    else:
        refresh_generated_files()
        service = node["container_name"]
    run_command(compose_args("up", "-d", service), dry_run=dry_run)
    storage.log_action("start", node_id)
    return storage.update_node(node_id, status="running", last_action="start")


def stop_node(node_id: str, *, dry_run: bool = False) -> dict:
    node = get_required_node(node_id)
    run_command(compose_args("stop", node["container_name"]), dry_run=dry_run)
    storage.log_action("stop", node_id)
    return storage.update_node(node_id, status="stopped", last_action="stop")


def restart_node(node_id: str, *, dry_run: bool = False) -> dict:
    node = get_required_node(node_id)
    run_command(compose_args("restart", node["container_name"]), dry_run=dry_run)
    storage.log_action("restart", node_id)
    return storage.update_node(node_id, status="running", last_action="restart")


def reset_chain(node_id: str, *, dry_run: bool = False) -> dict:
    node = get_required_node(node_id)
    node_path = ensure_child_path(NODES_DIR, NODES_DIR / Path(node["node_path"]).name)
    run_command(compose_args("stop", node["container_name"]), dry_run=dry_run)
    if node["node_type"] == "grinpp":
        targets = [node_path / "FLOONET" / "NODE", node_path / "FLOONET" / "LOGS" / "Node.log"]
    else:
        targets = [node_path / "chain_data", node_path / "grin-server.log"]
    if not dry_run:
        for target in targets:
            ensure_child_path(node_path, target)
            remove_path(target)
    run_command(compose_args("up", "-d", node["container_name"]), dry_run=dry_run)
    storage.log_action("reset-chain", node_id)
    return storage.update_node(node_id, status="running", sync_state="reset", last_action="reset-chain")


def delete_node(node_id: str, *, remove_files: bool = False, dry_run: bool = False) -> None:
    node = get_required_node(node_id)
    if node["node_type"] == "gateway":
        raise HTTPException(status_code=400, detail="gateway cannot be deleted")
    run_command(compose_args("stop", node["container_name"]), dry_run=dry_run)
    storage.delete_node(node_id)
    storage.log_action("delete", node_id)
    refresh_generated_files()
    if remove_files and not dry_run:
        node_path = ensure_child_path(NODES_DIR, NODES_DIR / Path(node["node_path"]).name)
        remove_path(node_path)
