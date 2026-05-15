import base64
import json
import os
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NODES = {}
SECRET = os.environ.get("GRIN_API_SECRET", "")
POLL_SECS = int(os.environ.get("GRIN_EXPORTER_POLL_SECS", "10"))
PORT = int(os.environ.get("GRIN_EXPORTER_PORT", "9108"))

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


def rpc(url, method, params=None):
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}).encode("utf-8")
    token = base64.b64encode(f"grin:{SECRET}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        f"{url}/v2/owner",
        data=body,
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        payload = json.loads(res.read().decode("utf-8"))
    result = payload.get("result", {})
    if "Err" in result:
        raise RuntimeError(result["Err"])
    return result.get("Ok")


def collect_once():
    for name, url in NODES.items():
        try:
            status = rpc(url, "get_status")
            peers = rpc(url, "get_connected_peers")
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
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def metric_line(name, labels, value):
    labels_text = ",".join(f'{k}="{esc(v)}"' for k, v in labels.items())
    return f"{name}{{{labels_text}}} {value}\n"


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

    for node, data in sorted(LAST.items()):
        out.append(metric_line("grin_node_up", {"node": node, "error": data["error"]}, data["ok"]))
        status = data.get("status") or {}
        tip = status.get("tip") or {}
        sync_status = status.get("sync_status", "unknown")
        out.append(metric_line("grin_node_height", {"node": node}, tip.get("height", 0)))
        out.append(metric_line("grin_node_total_difficulty", {"node": node}, tip.get("total_difficulty", 0)))
        out.append(metric_line("grin_node_connections", {"node": node}, status.get("connections", 0)))
        out.append(metric_line("grin_node_sync_status", {"node": node, "sync_status": sync_status}, STATUS_MAP.get(sync_status, -1)))
        for peer in data.get("peers") or []:
            labels = {
                "node": node,
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
    collect_once()
    threading.Thread(target=loop_collect, daemon=True).start()
    print(f"grin-exporter listening on :{PORT}/metrics for nodes: {', '.join(NODES)}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
