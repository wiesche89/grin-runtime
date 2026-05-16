import base64
import json
import os
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NODES = {}
NODE_META = {}
DEFAULT_SECRET = os.environ.get("GRIN_API_SECRET", "")
NODE_SECRETS = {}
POLL_SECS = int(os.environ.get("GRIN_EXPORTER_POLL_SECS", "10"))
PORT = int(os.environ.get("GRIN_EXPORTER_PORT", "9108"))
CONTROLLER_URL = os.environ.get("GRIN_CONTROLLER_URL", "").rstrip("/")

STATUS_MAP = {
    "no_sync": 0,
    "awaiting_peers": 1,
    "header_sync": 2,
    "body_sync": 3,
    "txhashset_download": 4,
    "txhashset_setup": 5,
    "txhashset_rangeproofs_validation": 6,
    "txhashset_kernels_validation": 7,
    "txhashset_save": 8,
    "txhashset_done": 9,
    "txhashset_pibd": 10,
}

LAST = {}


def parse_nodes():
    raw = os.environ.get("GRIN_NODES", "")
    nodes = {}
    for item in raw.split(","):
        if not item.strip():
            continue
        name, url = item.split("=", 1)
        nodes[name.strip()] = url.strip().rstrip("/")
    return nodes


def controller_nodes():
    if not CONTROLLER_URL:
        return {}, {}
    req = urllib.request.Request(f"{CONTROLLER_URL}/api/nodes", method="GET")
    with urllib.request.urlopen(req, timeout=10) as res:
        payload = json.loads(res.read().decode("utf-8"))
    nodes = {}
    meta = {}
    for item in payload:
        if item.get("status") == "deleted":
            continue
        name = item["node_name"]
        nodes[name] = f"http://{item['container_name']}:13413"
        meta[name] = item
    return nodes, meta


def parse_node_secrets():
    raw = os.environ.get("GRIN_NODE_SECRETS", "")
    secrets = {}
    for item in raw.split(","):
        if not item.strip():
            continue
        name, secret = item.split("=", 1)
        secrets[name.strip()] = secret.strip()
    return secrets


def rpc(node, url, method, params=None):
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}).encode("utf-8")
    secret = NODE_SECRETS.get(node, DEFAULT_SECRET)
    headers = {"Content-Type": "application/json"}
    if secret:
        token = base64.b64encode(f"grin:{secret}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(
        f"{url}/v2/owner",
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        payload = json.loads(res.read().decode("utf-8"))
    result = payload.get("result", {})
    if "Err" in result:
        raise RuntimeError(result["Err"])
    return result.get("Ok")


def collect_once():
    global NODES, NODE_META
    try:
        dynamic_nodes, dynamic_meta = controller_nodes()
        if dynamic_nodes:
            NODES = dynamic_nodes
            NODE_META = dynamic_meta
    except Exception as err:
        print(f"[WARN] controller discovery failed: {err}", flush=True)
    for name, url in NODES.items():
        try:
            status = rpc(name, url, "get_status")
            peers = rpc(name, url, "get_connected_peers")
            LAST[name] = {
                "ok": 1,
                "error": "",
                "status": status,
                "peers": peers,
                "updated": time.time(),
            }
        except Exception as err:
            LAST[name] = {
                "ok": 0,
                "error": str(err).replace("\n", " ")[:160],
                "status": None,
                "peers": [],
                "updated": time.time(),
            }


def loop_collect():
    while True:
        collect_once()
        time.sleep(POLL_SECS)


def esc(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace('"', '\\"')


def metric_line(name, labels, value):
    labels_text = ",".join(f'{k}="{esc(v)}"' for k, v in labels.items())
    return f"{name}{{{labels_text}}} {value}\n"


def node_labels(node):
    meta = NODE_META.get(node, {})
    node_id = meta.get("node_id", node)
    node_name = meta.get("node_name", node)
    return {
        "node": node_name,
        "node_id": node_id,
        "node_name": node_name,
        "node_type": meta.get("node_type", "unknown"),
        "profile": meta.get("profile", ""),
        "experiment_id": meta.get("experiment_id") or "",
        "image_tag": meta.get("image_tag") or "",
        "commit_hash": meta.get("git_commit_hash") or "",
        "autosync_enabled": str(bool(meta.get("autosync_enabled", False))).lower(),
        "failure_state": meta.get("failure_state", "unknown"),
    }


def flatten_status(value, prefix=""):
    if isinstance(value, dict):
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else key
            yield from flatten_status(value[key], path)
    elif isinstance(value, list):
        yield prefix, json.dumps(value, separators=(",", ":"))
    elif value is not None:
        yield prefix, value


def flatten_info(value, prefix=""):
    yield from flatten_status(value, prefix)


def status_field_lines(node, status):
    lines = []
    for path, value in flatten_status(status):
        lines.append(metric_line("grin_status_field_info", {"node": node, "path": path, "value": value}, 1))
    return lines


def peer_field_lines(node, peers):
    lines = []
    for index, peer in enumerate(peers or []):
        peer_addr = peer.get("addr", f"peer-{index}")
        direction = peer.get("direction", "unknown")
        for path, value in flatten_info(peer):
            lines.append(metric_line(
                "grin_peer_field_info",
                {"node": node, "peer": peer_addr, "direction": direction, "path": path, "value": value},
                1,
            ))
    return lines


def connection_count(status, peers):
    return max(int(status.get("connections", 0) or 0), len(peers or []))


def render_metrics():
    out = []
    out.append("# HELP grin_node_up Whether API v2 polling succeeded.\n")
    out.append("# TYPE grin_node_up gauge\n")
    out.append("# HELP grin_node_height Current node chain height.\n")
    out.append("# TYPE grin_node_height gauge\n")
    out.append("# HELP grin_node_total_difficulty Current node total difficulty.\n")
    out.append("# TYPE grin_node_total_difficulty gauge\n")
    out.append("# HELP grin_node_connections Number of connected peers.\n")
    out.append("# TYPE grin_node_connections gauge\n")
    out.append("# HELP grin_node_sync_status Numeric sync status code with sync_status label.\n")
    out.append("# TYPE grin_node_sync_status gauge\n")
    out.append("# HELP grin_peer_height Connected peer advertised height.\n")
    out.append("# TYPE grin_peer_height gauge\n")
    out.append("# HELP grin_peer_total_difficulty Connected peer total difficulty.\n")
    out.append("# TYPE grin_peer_total_difficulty gauge\n")
    out.append("# HELP grin_status_field_info Selected raw fields from get_status as label values.\n")
    out.append("# TYPE grin_status_field_info gauge\n")
    out.append("# HELP grin_peer_field_info Raw fields from get_connected_peers as label values.\n")
    out.append("# TYPE grin_peer_field_info gauge\n")

    for node, data in sorted(LAST.items()):
        labels = node_labels(node)
        out.append(metric_line("grin_node_up", {**labels, "error": data["error"]}, data["ok"]))
        status = data.get("status") or {}
        peers = data.get("peers") or []
        tip = status.get("tip") or {}
        sync_status = status.get("sync_status", "unknown")
        out.append(metric_line("grin_node_height", labels, tip.get("height", 0)))
        out.append(metric_line("grin_node_total_difficulty", labels, tip.get("total_difficulty", 0)))
        out.append(metric_line("grin_node_connections", labels, connection_count(status, peers)))
        out.append(metric_line("grin_node_sync_status", {**labels, "sync_status": sync_status}, STATUS_MAP.get(sync_status, -1)))
        out.extend(status_field_lines(node, status))
        out.extend(peer_field_lines(node, peers))
        for peer in peers:
            labels = {
                **node_labels(node),
                "peer": peer.get("addr", "unknown"),
                "direction": peer.get("direction", "unknown"),
                "user_agent": peer.get("user_agent", "unknown"),
            }
            out.append(metric_line("grin_peer_height", labels, peer.get("height", 0)))
            out.append(metric_line("grin_peer_total_difficulty", labels, peer.get("total_difficulty", 0)))
    return "".join(out).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        body = render_metrics()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    import threading

    NODES = parse_nodes()
    NODE_SECRETS = parse_node_secrets()
    collect_once()
    threading.Thread(target=loop_collect, daemon=True).start()
    print(f"grin-exporter listening on :{PORT}/metrics for nodes: {', '.join(NODES)}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
