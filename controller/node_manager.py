from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

from fastapi import HTTPException

from . import compose_generator, config_generator, monitoring_generator, storage
from .models import NodeCreate
from .security import ensure_child_path, validate_node_id
from .utils import NODES_DIR, REPO_ROOT, RuntimeCommandError, compose_args, remove_path, run_command, utcnow_iso


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
    if NODES_DIR.exists():
        for path in NODES_DIR.iterdir():
            if not path.is_dir() or not path.name.startswith(prefix):
                continue
            try:
                used.add(int(path.name.removeprefix(prefix)))
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


def image_metadata(image: str, tag: str) -> dict[str, str | None]:
    ref = f"{image}:{tag}"
    try:
        completed = subprocess.run(
            ["docker", "image", "inspect", ref, "--format", "{{json .}}"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return {"image_digest": None, "git_commit_hash": os.environ.get("GRIN_GIT_COMMIT"), "build_date": os.environ.get("GRIN_BUILD_DATE")}
    import json

    payload = json.loads(completed.stdout)
    labels = payload.get("Config", {}).get("Labels") or {}
    repo_digests = payload.get("RepoDigests") or []
    return {
        "image_digest": repo_digests[0].split("@", 1)[1] if repo_digests and "@" in repo_digests[0] else payload.get("Id"),
        "git_commit_hash": labels.get("org.opencontainers.image.revision") or labels.get("git_commit") or os.environ.get("GRIN_GIT_COMMIT"),
        "build_date": labels.get("org.opencontainers.image.created") or os.environ.get("GRIN_BUILD_DATE"),
    }


def create_node(payload: NodeCreate) -> dict:
    enforce_resource_limits()
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
    image_meta = image_metadata(docker_image, image_tag)
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
        "image_digest": image_meta["image_digest"],
        "git_commit_hash": image_meta["git_commit_hash"],
        "build_date": image_meta["build_date"],
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
        try:
            start_node(node_id)
        except RuntimeCommandError as err:
            storage.update_node(
                node_id,
                status="failed",
                failure_state="container_stopped",
                last_action="start-failed",
            )
            storage.log_action("start-failed", node_id, str(err))
            raise HTTPException(status_code=502, detail=f"node was created but container start failed: {err}") from err
    return storage.get_node(node_id)


def enforce_resource_limits() -> None:
    host_root = os.environ.get("RUNTIME_DOCKER_HOST_ROOT", "")
    if not host_root or not Path(host_root).is_absolute():
        raise HTTPException(
            status_code=503,
            detail="RUNTIME_DOCKER_HOST_ROOT must be set to the absolute host repository path",
        )
    max_nodes = int(os.environ.get("RUNTIME_MAX_WORKER_NODES", "100"))
    active_workers = [node for node in storage.list_nodes() if node["node_type"] != "gateway" and node["status"] != "deleted"]
    if len(active_workers) >= max_nodes:
        raise HTTPException(status_code=429, detail="worker node limit reached")
    total, _used, free = __import__("shutil").disk_usage(REPO_ROOT)
    min_free_gb = float(os.environ.get("RUNTIME_MIN_FREE_DISK_GB", "2"))
    if free < min_free_gb * 1024 * 1024 * 1024:
        raise HTTPException(status_code=429, detail="not enough free disk space to create node")


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
    sync_run_id = f"sync-{uuid.uuid4().hex[:12]}"
    updated = storage.update_node(node_id, status="running", sync_state="starting", sync_run_id=sync_run_id, last_action="start")
    if updated["node_type"] != "gateway":
        storage.start_benchmark_run(updated, sync_run_id)
    return updated


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
        targets = [node_path / "FLOONET"]
    else:
        targets = [node_path / "chain_data", node_path / "grin-server.log"]
    if not dry_run:
        for target in targets:
            ensure_child_path(node_path, target)
            remove_path(target)
        if node["node_type"] == "grinpp":
            config_generator.generate_grinpp_config(node_id, node["profile"])
    run_command(compose_args("up", "-d", node["container_name"]), dry_run=dry_run)
    storage.log_action("reset-chain", node_id)
    sync_run_id = f"sync-{uuid.uuid4().hex[:12]}"
    updated = storage.update_node(node_id, status="running", sync_state="reset", sync_run_id=sync_run_id, last_action="reset-chain")
    if updated["node_type"] != "gateway":
        storage.start_benchmark_run(updated, sync_run_id)
    return updated


def delete_node(node_id: str, *, remove_files: bool = False, dry_run: bool = False) -> None:
    node = get_required_node(node_id)
    if node["node_type"] == "gateway":
        raise HTTPException(status_code=400, detail="gateway cannot be deleted")
    run_command(compose_args("stop", node["container_name"]), dry_run=dry_run)
    run_command(compose_args("rm", "-f", node["container_name"]), dry_run=dry_run)
    storage.delete_node(node_id)
    storage.log_action("delete", node_id)
    refresh_generated_files()
    if remove_files and not dry_run:
        node_path = ensure_child_path(NODES_DIR, NODES_DIR / Path(node["node_path"]).name)
        remove_path(node_path)
