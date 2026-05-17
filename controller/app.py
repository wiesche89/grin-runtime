from __future__ import annotations

import os
import shutil
from html import escape
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from . import autosync_manager, benchmark_manager, experiment_manager, node_manager, scheduler, storage
from .models import ExperimentCreate, NodeActionResult, NodeCreate, NodeRecord, SystemHealth
from .security import require_write_token, validate_node_id, write_auth_required


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.init_db()
    node_manager.refresh_generated_files()
    scheduler.start_background_scheduler(int(os.environ.get("RUNTIME_SCHEDULER_INTERVAL", "30")))
    yield


app = FastAPI(title="Grin Runtime Controller", version="0.1.0", lifespan=lifespan)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": "grin-runtime-controller", "ui": "/ui", "health": "/api/system/health"}


@app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
def control_ui() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Grin Runtime Control</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #111217; color: #e8eaf0; }
    main { padding: 16px; }
    .bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 14px; }
    input, select, button { border: 1px solid #343946; background: #191c24; color: #e8eaf0; border-radius: 4px; padding: 8px 10px; font-size: 13px; }
    button { cursor: pointer; background: #263247; }
    button:hover { background: #31405c; }
    button.danger { background: #4a2026; border-color: #7b2e39; }
    button.danger:hover { background: #642934; }
    button.good { background: #1f432e; border-color: #2b7044; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid #272b35; padding: 9px 8px; text-align: left; vertical-align: middle; font-size: 13px; }
    th { color: #aeb7c8; font-weight: 600; }
    .actions { display: flex; flex-wrap: wrap; gap: 6px; }
    .muted { color: #aeb7c8; }
    .pill { border: 1px solid #343946; border-radius: 999px; padding: 2px 8px; font-size: 12px; }
    #message { min-height: 20px; margin: 8px 0 12px; color: #b7d3ff; }
  </style>
</head>
<body>
<main>
  <div class="bar">
    <input id="token" type="password" placeholder="Runtime token" autocomplete="off">
    <select id="nodeType">
      <option value="grin-rust">Grin Rust</option>
      <option value="grinpp">Grin++</option>
    </select>
    <select id="profile">
      <option value="default">default</option>
      <option value="pihd-test">pihd-test</option>
      <option value="pibd-test">pibd-test</option>
      <option value="benchmark">benchmark</option>
      <option value="low-memory">low-memory</option>
      <option value="high-peers">high-peers</option>
      <option value="archive">archive</option>
      <option value="pruned">pruned</option>
      <option value="grinpp-compat">grinpp-compat</option>
    </select>
    <button class="good" onclick="createNode()">Add Node</button>
    <button onclick="loadNodes()">Refresh</button>
  </div>
  <div id="message" class="muted"></div>
  <table>
    <thead>
      <tr>
        <th>Node</th>
        <th>Type</th>
        <th>Profile</th>
        <th>Status</th>
        <th>Autosync</th>
        <th>Failure</th>
        <th>Image</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody id="nodes"></tbody>
  </table>
</main>
<script>
const tokenInput = document.getElementById("token");
const apiBase = window.location.pathname.endsWith("/ui") ? window.location.pathname.slice(0, -3) : "";
tokenInput.value = localStorage.getItem("runtimeToken") || "";
tokenInput.addEventListener("change", () => localStorage.setItem("runtimeToken", tokenInput.value));
let authRequired = true;

function msg(text, isError=false) {
  const el = document.getElementById("message");
  el.textContent = text;
  el.style.color = isError ? "#ffb3bc" : "#b7d3ff";
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (authRequired && options.method && options.method !== "GET") {
    headers["X-Runtime-Token"] = tokenInput.value;
  }
  if (options.body) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${apiBase}${path}`, {...options, headers});
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (_) { data = text; }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : text;
    throw new Error(detail || res.statusText);
  }
  return data;
}

function button(label, action, nodeId, danger=false) {
  return `<button class="${danger ? "danger" : ""}" onclick="nodeAction('${nodeId}', '${action}')">${label}</button>`;
}

async function loadNodes() {
  try {
    const nodes = await api("/api/nodes");
    const body = document.getElementById("nodes");
    body.innerHTML = nodes.map(n => {
      const autosyncAction = n.autosync_enabled ? "autosync/disable" : "autosync/enable";
      const autosyncLabel = n.autosync_enabled ? "Disable Autosync" : "Enable Autosync";
      const deleteButton = n.node_type === "gateway" ? "" : button("Delete", "delete", n.node_id, true);
      return `<tr>
        <td><strong>${n.node_name}</strong><br><span class="muted">${n.node_id}</span></td>
        <td>${n.node_type}</td>
        <td>${n.profile}</td>
        <td><span class="pill">${n.status}</span></td>
        <td>${n.autosync_enabled ? "enabled" : "disabled"}</td>
        <td>${n.failure_state}</td>
        <td>${n.docker_image}:${n.image_tag}</td>
        <td class="actions">
          ${button("Start", "start", n.node_id)}
          ${button("Stop", "stop", n.node_id)}
          ${button("Restart", "restart", n.node_id)}
          ${button("Reset Chain", "reset-chain", n.node_id, true)}
          ${button(autosyncLabel, autosyncAction, n.node_id)}
          ${deleteButton}
        </td>
      </tr>`;
    }).join("");
    msg(`Loaded ${nodes.length} nodes.`);
  } catch (err) {
    msg(err.message, true);
  }
}

async function createNode() {
  try {
    const payload = {
      node_type: document.getElementById("nodeType").value,
      profile: document.getElementById("profile").value
    };
    const node = await api("/api/nodes", {method: "POST", body: JSON.stringify(payload)});
    msg(`Created ${node.node_name}.`);
    await loadNodes();
  } catch (err) {
    msg(err.message, true);
  }
}

async function nodeAction(nodeId, action) {
  try {
    if (action === "delete") {
      if (!confirm(`Delete ${nodeId}?`)) return;
      await api(`/api/nodes/${nodeId}?remove_files=true`, {method: "DELETE"});
      msg(`Deleted ${nodeId}.`);
    } else {
      await api(`/api/nodes/${nodeId}/${action}`, {method: "POST"});
      msg(`${action} completed for ${nodeId}.`);
    }
    await loadNodes();
  } catch (err) {
    msg(err.message, true);
  }
}

loadNodes();
loadSecurity();
setInterval(loadNodes, 10000);

async function loadSecurity() {
  try {
    const security = await api("/api/system/security");
    authRequired = Boolean(security.write_auth_required);
    tokenInput.style.display = authRequired ? "" : "none";
  } catch (_) {
    authRequired = true;
  }
}
</script>
</body>
</html>
"""


def table_page(title: str, rows: list[dict], columns: list[str]) -> str:
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{escape(str(row.get(column, '') or ''))}</td>" for column in columns) + "</tr>"
    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #111217; color: #e8eaf0; }}
    main {{ padding: 16px; }}
    h1 {{ font-size: 16px; margin: 0 0 14px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #272b35; padding: 9px 8px; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ color: #aeb7c8; font-weight: 600; position: sticky; top: 0; background: #111217; }}
  </style>
</head>
<body><main>
  <h1>{escape(title)}</h1>
  <table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>
</main></body>
</html>
"""


@app.get("/ui/benchmarks", response_class=HTMLResponse, include_in_schema=False)
def benchmark_ui() -> str:
    columns = [
        "id", "node_name", "node_type", "profile", "experiment_id", "sync_run_id", "sync_started_at",
        "sync_completed_at", "total_sync_duration", "header_sync_duration", "PIHD_duration",
        "PIBD_duration", "rangeproof_validation_duration", "kernel_validation_duration", "final_height",
        "average_peer_count", "max_cpu_usage", "max_ram_usage", "max_disk_io", "result", "error_message",
    ]
    return table_page("Benchmark History", storage.list_benchmarks(), columns)


@app.get("/ui/experiments", response_class=HTMLResponse, include_in_schema=False)
def experiment_ui() -> str:
    columns = ["experiment_id", "experiment_name", "description", "status", "created_at", "started_at", "stopped_at", "node_profiles_json", "labels_json"]
    return table_page("Experiments", storage.list_experiments(), columns)


@app.get("/ui/failures", response_class=HTMLResponse, include_in_schema=False)
def failure_ui() -> str:
    nodes = storage.list_nodes()
    rows = []
    for node in nodes:
        latest = storage.latest_observation(node["node_id"]) or {}
        rows.append({**node, **{f"latest_{key}": value for key, value in latest.items()}})
    columns = [
        "node_id", "node_name", "node_type", "profile", "status", "failure_state", "sync_state",
        "latest_observed_at", "latest_api_up", "latest_container_running", "latest_height",
        "latest_header_height", "latest_peer_count", "latest_cpu_percent", "latest_ram_bytes",
        "latest_error_message",
    ]
    return table_page("Failure Dashboard", rows, columns)


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


@app.get("/api/nodes/{node_id}/observations")
def node_observations(node_id: str, limit: int = Query(default=50, ge=1, le=500)) -> list[dict]:
    validate_node_id(node_id)
    return storage.recent_observations(node_id, limit)


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


@app.get("/api/system/security")
def system_security() -> dict:
    return {"write_auth_required": write_auth_required()}


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
        "# HELP grin_runtime_node_observation Latest controller observation values.",
        "# TYPE grin_runtime_node_observation gauge",
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
        observation = storage.latest_observation(node["node_id"])
        if observation:
            for key in ("api_up", "container_running", "height", "header_height", "peer_count", "cpu_percent", "ram_bytes", "disk_read_bytes", "disk_write_bytes", "network_rx_bytes", "network_tx_bytes"):
                value = observation.get(key)
                if value is not None:
                    lines.append(f'grin_runtime_node_observation{{{labels},metric="{key}"}} {value}')
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
    return experiment_manager.start_experiment(experiment_id)


@app.post("/api/experiments/{experiment_id}/stop", dependencies=[Depends(require_write_token)])
def stop_experiment(experiment_id: str) -> dict:
    return experiment_manager.stop_experiment(experiment_id)
