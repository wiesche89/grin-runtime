from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import urllib.request
from typing import Any


DEFAULT_SECRET = os.environ.get("GRIN_API_SECRET", "node-test-owner-secret")


def rpc(node: dict, method: str, params: list | None = None) -> Any:
    secret = "" if node["node_type"] == "grinpp" else DEFAULT_SECRET
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if secret:
        token = base64.b64encode(f"grin:{secret}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(
        f"http://{node['container_name']}:13413/v2/owner",
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=8) as res:
        payload = json.loads(res.read().decode("utf-8"))
    result = payload.get("result", {})
    if "Err" in result:
        raise RuntimeError(result["Err"])
    return result.get("Ok")


def docker_json(args: list[str]) -> dict | list | None:
    try:
        completed = subprocess.run(
            ["docker", *args],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    text = completed.stdout.strip()
    if not text:
        return None
    if "\n" in text:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def container_running(container_name: str) -> bool:
    payload = docker_json(["inspect", container_name, "--format", "{{json .State}}"])
    return bool(payload and payload.get("Running"))


def parse_size(value: str) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)\s*", value)
    if not match:
        return None
    number, unit = match.groups()
    multipliers = {
        "B": 1,
        "kB": 1000,
        "KB": 1000,
        "KiB": 1024,
        "MB": 1000**2,
        "MiB": 1024**2,
        "GB": 1000**3,
        "GiB": 1024**3,
    }
    try:
        return int(float(number) * multipliers.get(unit, 1))
    except ValueError:
        return None


def parse_pair(value: str) -> tuple[int | None, int | None]:
    if not value or "/" not in value:
        return None, None
    left, right = value.split("/", 1)
    return parse_size(left.strip()), parse_size(right.strip())


def container_stats(container_name: str) -> dict[str, Any]:
    payload = docker_json(["stats", "--no-stream", "--format", "{{json .}}", container_name])
    if not isinstance(payload, dict):
        return {}
    mem_used, _mem_limit = parse_pair(payload.get("MemUsage", ""))
    block_read, block_write = parse_pair(payload.get("BlockIO", ""))
    net_rx, net_tx = parse_pair(payload.get("NetIO", ""))
    cpu_text = str(payload.get("CPUPerc", "0")).replace("%", "")
    try:
        cpu = float(cpu_text)
    except ValueError:
        cpu = None
    return {
        "cpu_percent": cpu,
        "ram_bytes": mem_used,
        "disk_read_bytes": block_read,
        "disk_write_bytes": block_write,
        "network_rx_bytes": net_rx,
        "network_tx_bytes": net_tx,
    }


def collect_node_observation(node: dict) -> dict[str, Any]:
    running = container_running(node["container_name"])
    stats = container_stats(node["container_name"]) if running else {}
    observation: dict[str, Any] = {
        "api_up": 0,
        "container_running": 1 if running else 0,
        "sync_state": node.get("sync_state") or "unknown",
        "height": None,
        "header_height": None,
        "peer_count": None,
        "error_message": None,
        **stats,
    }
    if not running:
        observation["error_message"] = "container is not running"
        return observation
    try:
        status = rpc(node, "get_status") or {}
        peers = rpc(node, "get_connected_peers") or []
        tip = status.get("tip") or {}
        observation.update(
            {
                "api_up": 1,
                "sync_state": status.get("sync_status") or "unknown",
                "height": tip.get("height"),
                "header_height": status.get("header_head", {}).get("height") if isinstance(status.get("header_head"), dict) else None,
                "peer_count": max(int(status.get("connections", 0) or 0), len(peers)),
            }
        )
    except Exception as err:
        observation["error_message"] = str(err)[:240]
    return observation
