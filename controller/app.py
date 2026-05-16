from __future__ import annotations

import os
import shutil
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query
from fastapi.responses import PlainTextResponse

from . import autosync_manager, benchmark_manager, experiment_manager, node_manager, scheduler, storage
from .models import ExperimentCreate, NodeActionResult, NodeCreate, NodeRecord, SystemHealth
from .security import require_write_token, validate_node_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.init_db()
    node_manager.refresh_generated_files()
    scheduler.start_background_scheduler(int(os.environ.get("RUNTIME_SCHEDULER_INTERVAL", "30")))
    yield


app = FastAPI(title="Grin Runtime Controller", version="0.1.0", lifespan=lifespan)


@app.get("/api/nodes", response_model=list[NodeRecord])
def list_nodes() -> list[dict]:
    return storage.list_nodes()


@app.post("/api/nodes", response_model=NodeRecord, dependencies=[Depends(require_write_token)])
def create_node(payload: NodeCreate) -> dict:
    return node_manager.create_node(payload)


@app.delete("/api/nodes/{node_id}", dependencies=[Depends(require_write_token)])
def delete_node(node_id: str, remove_files: bool = Query(default=False)) -> dict:
    validate_node_id(node_id)
    node_manager.delete_node(node_id, remove_files=remove_files)
    return {"status": "deleted", "node_id": node_id}


@app.post("/api/nodes/{node_id}/start", response_model=NodeActionResult, dependencies=[Depends(require_write_token)])
def start_node(node_id: str) -> dict:
    validate_node_id(node_id)
    return {"node": node_manager.start_node(node_id), "action": "start"}


@app.post("/api/nodes/{node_id}/stop", response_model=NodeActionResult, dependencies=[Depends(require_write_token)])
def stop_node(node_id: str) -> dict:
    validate_node_id(node_id)
    return {"node": node_manager.stop_node(node_id), "action": "stop"}


@app.post("/api/nodes/{node_id}/restart", response_model=NodeActionResult, dependencies=[Depends(require_write_token)])
def restart_node(node_id: str) -> dict:
    validate_node_id(node_id)
    return {"node": node_manager.restart_node(node_id), "action": "restart"}


@app.post("/api/nodes/{node_id}/reset-chain", response_model=NodeActionResult, dependencies=[Depends(require_write_token)])
def reset_chain(node_id: str) -> dict:
    validate_node_id(node_id)
    return {"node": node_manager.reset_chain(node_id), "action": "reset-chain"}


@app.post("/api/nodes/{node_id}/autosync/enable", response_model=NodeActionResult, dependencies=[Depends(require_write_token)])
def enable_autosync(node_id: str) -> dict:
    validate_node_id(node_id)
    return {"node": autosync_manager.set_autosync(node_id, True), "action": "autosync-enable"}


@app.post("/api/nodes/{node_id}/autosync/disable", response_model=NodeActionResult, dependencies=[Depends(require_write_token)])
def disable_autosync(node_id: str) -> dict:
    validate_node_id(node_id)
    return {"node": autosync_manager.set_autosync(node_id, False), "action": "autosync-disable"}


@app.get("/api/system/resources")
def system_resources() -> dict:
    total, used, free = shutil.disk_usage(os.environ.get("RUNTIME_REPO_ROOT", "."))
    nodes = storage.list_nodes()
    mem = read_meminfo()
    return {
        "load_average": read_load_average(),
        "host_ram_percent": mem.get("ram_percent"),
        "swap_percent": mem.get("swap_percent"),
        "disk_total_bytes": total,
        "disk_used_bytes": used,
        "disk_free_bytes": free,
        "running_node_count": len([node for node in nodes if node["status"] == "running"]),
        "node_count": len(nodes),
    }


def read_load_average() -> dict | None:
    try:
        one, five, fifteen = os.getloadavg()
        return {"1m": one, "5m": five, "15m": fifteen}
    except OSError:
        return None


def read_meminfo() -> dict:
    try:
        values = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as meminfo:
            for line in meminfo:
                key, raw = line.split(":", 1)
                values[key] = int(raw.strip().split()[0]) * 1024
        total = values.get("MemTotal", 0)
        available = values.get("MemAvailable", 0)
        swap_total = values.get("SwapTotal", 0)
        swap_free = values.get("SwapFree", 0)
        return {
            "ram_percent": round(((total - available) / total) * 100, 2) if total else None,
            "swap_percent": round(((swap_total - swap_free) / swap_total) * 100, 2) if swap_total else 0,
        }
    except (FileNotFoundError, ValueError, IndexError):
        return {"ram_percent": None, "swap_percent": None}


@app.get("/api/system/health", response_model=SystemHealth)
def system_health() -> dict:
    nodes = storage.list_nodes()
    failures = len([node for node in nodes if node.get("failure_state") not in ("ok", "unknown")])
    return {
        "status": "degraded" if failures else "ok",
        "node_count": len(nodes),
        "running_node_count": len([node for node in nodes if node["status"] == "running"]),
        "failures": failures,
    }


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    nodes = storage.list_nodes()
    lines = [
        "# HELP grin_runtime_nodes Registered runtime nodes.",
        "# TYPE grin_runtime_nodes gauge",
        "# HELP grin_runtime_autosync_enabled Autosync enabled per node.",
        "# TYPE grin_runtime_autosync_enabled gauge",
        "# HELP grin_runtime_failure_state Node failure state as labelled info metric.",
        "# TYPE grin_runtime_failure_state gauge",
    ]
    lines.append(f"grin_runtime_nodes {len(nodes)}")
    for node in nodes:
        labels = ",".join(
            f'{key}="{str(value).replace(chr(34), chr(92) + chr(34))}"'
            for key, value in {
                "node_id": node["node_id"],
                "node_name": node["node_name"],
                "node_type": node["node_type"],
                "profile": node["profile"],
                "experiment_id": node.get("experiment_id") or "",
                "status": node["status"],
                "failure_state": node.get("failure_state") or "unknown",
            }.items()
        )
        lines.append(f"grin_runtime_autosync_enabled{{{labels}}} {1 if node.get('autosync_enabled') else 0}")
        lines.append(f"grin_runtime_failure_state{{{labels}}} 1")
    return "\n".join(lines) + "\n"


@app.get("/api/benchmarks")
def benchmarks() -> list[dict]:
    return benchmark_manager.list_benchmarks()


@app.get("/api/experiments")
def experiments() -> list[dict]:
    return experiment_manager.list_experiments()


@app.post("/api/experiments", dependencies=[Depends(require_write_token)])
def create_experiment(payload: ExperimentCreate) -> dict:
    return experiment_manager.create_experiment(payload)


@app.post("/api/experiments/{experiment_id}/start", dependencies=[Depends(require_write_token)])
def start_experiment(experiment_id: str) -> dict:
    return {"experiment_id": experiment_id, "status": "started"}


@app.post("/api/experiments/{experiment_id}/stop", dependencies=[Depends(require_write_token)])
def stop_experiment(experiment_id: str) -> dict:
    return {"experiment_id": experiment_id, "status": "stopped"}
