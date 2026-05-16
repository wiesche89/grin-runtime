import base64
import json
import os
import time
import urllib.error
import urllib.request

BAD_LOG_PATTERNS = (
    "Header batch cache full",
    "throttling PIHD header segment request",
    "BadHeader",
    "BadBlockHeader",
    "failed to send",
    "Failed to send",
    "try_send disconnected",
    "falling back to TxHashset.zip",
    "PIHD header sync aborted",
    "PIBD aborted",
)


def parse_nodes():
    raw = os.environ.get("GRIN_NODES", "")
    nodes = {}
    for item in raw.split(","):
        if not item.strip():
            continue
        name, url = item.split("=", 1)
        nodes[name.strip()] = url.strip().rstrip("/")
    return nodes


def controller_nodes(controller_url):
    if not controller_url:
        return {}, {}, set()
    req = urllib.request.Request(f"{controller_url.rstrip('/')}/api/nodes", method="GET")
    with urllib.request.urlopen(req, timeout=10) as res:
        payload = json.loads(res.read().decode("utf-8"))
    nodes = {}
    log_files = {}
    internal = set()
    for item in payload:
        if item.get("status") == "deleted":
            continue
        name = item["node_name"]
        nodes[name] = f"http://{item['container_name']}:13413"
        if item["node_type"] == "grinpp":
            log_files[name] = f"/nodes/{item['node_id']}/FLOONET/LOGS/Node.log"
        else:
            log_files[name] = f"/nodes/{item['node_id']}/grin-server.log"
        if item["node_type"] != "gateway":
            internal.add(name)
    return nodes, log_files, internal


def parse_log_files():
    raw = os.environ.get("GRIN_LOG_FILES", "")
    files = {}
    for item in raw.split(","):
        if not item.strip():
            continue
        name, path = item.split("=", 1)
        files[name.strip()] = path.strip()
    return files


def parse_node_secrets():
    raw = os.environ.get("GRIN_NODE_SECRETS", "")
    secrets = {}
    for item in raw.split(","):
        if not item.strip():
            continue
        name, secret = item.split("=", 1)
        secrets[name.strip()] = secret.strip()
    return secrets


def rpc(url, secret, method, params=None):
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}).encode("utf-8")
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


def scan_log(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as log_file:
            lines = log_file.readlines()[-500:]
    except FileNotFoundError:
        return []
    return [line.strip() for line in lines if any(pattern in line for pattern in BAD_LOG_PATTERNS)]


def connection_count(status, peers):
    return max(int(status.get("connections", 0) or 0), len(peers or []))


def main():
    nodes = parse_nodes()
    controller_url = os.environ.get("GRIN_CONTROLLER_URL", "")
    default_secret = os.environ.get("GRIN_API_SECRET", "")
    node_secrets = parse_node_secrets()
    poll_secs = int(os.environ.get("GRIN_POLL_SECS", "15"))
    height_lag_warn = int(os.environ.get("GRIN_HEIGHT_LAG_WARN", "2"))
    internal_nodes = {item.strip() for item in os.environ.get("GRIN_INTERNAL_NODES", "").split(",") if item.strip()}
    log_files = parse_log_files()

    while True:
        try:
            dynamic_nodes, dynamic_logs, dynamic_internal = controller_nodes(controller_url)
            if dynamic_nodes:
                nodes = dynamic_nodes
                log_files = dynamic_logs
                internal_nodes = dynamic_internal
        except Exception as err:
            print(f"[WARN] controller discovery failed: {err}", flush=True)
        statuses = {}
        for name, url in nodes.items():
            try:
                secret = node_secrets.get(name, default_secret)
                status = rpc(url, secret, "get_status")
                peers = rpc(url, secret, "get_connected_peers")
                statuses[name] = {
                    "height": status["tip"]["height"],
                    "sync_status": status["sync_status"],
                    "connections": connection_count(status, peers),
                    "peers": peers,
                }
            except (urllib.error.URLError, TimeoutError, RuntimeError, KeyError) as err:
                print(f"[WARN] {name}: API v2 unavailable: {err}", flush=True)

        if statuses:
            max_height = max(item["height"] for item in statuses.values())
            for name, status in statuses.items():
                lag = max_height - status["height"]
                msg = f"[STATUS] {name}: height={status['height']} lag={lag} sync={status['sync_status']} peers={status['connections']}"
                if lag > height_lag_warn:
                    msg = "[WARN] " + msg
                print(msg, flush=True)
                if name in internal_nodes and status["connections"] == 0:
                    print(f"[WARN] {name}: internal node has no peers", flush=True)
                bad_lines = scan_log(log_files.get(name, ""))
                if bad_lines:
                    print(f"[WARN] {name}: suspicious log lines:", flush=True)
                    for line in bad_lines[-10:]:
                        print(f"  {line}", flush=True)
        time.sleep(poll_secs)


if __name__ == "__main__":
    main()
