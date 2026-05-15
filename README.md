# Grin Runtime

Separate Docker integration test project for the Grin staging branch.

## Topology

- `grin-gw`: public + internal Docker network, can reach external peers.
- `grin-node-1`, `grin-node-2`: internal Docker network only.
- `grinpp-node-1`: Grin++ floonet node built from `wiesche89/grinplusplus` `master`, internal Docker network only.
- `monitor`: polls API v2 owner JSON-RPC and scans mounted logs.
- `grin-exporter`: exposes Prometheus metrics from API v2.
- `prometheus`: scrapes `grin-exporter`.
- `grafana`: pre-provisioned Prometheus datasource and dashboard.

## Run

```bash
docker compose up --build
```

By default the Grin image is built from:

```text
https://github.com/wiesche89/grin.git branch staging
```

The Grin++ image is built from:

```text
https://github.com/wiesche89/grinplusplus.git branch master
```

Override when needed:

```bash
GRIN_REPO=https://github.com/wiesche89/grin.git GRIN_BRANCH=staging docker compose up --build
GRINPP_REPO=https://github.com/wiesche89/grinplusplus.git GRINPP_REF=master docker compose up --build
```

## UI

```text
Grafana:    http://<vm-ip>:3000    admin / admin
Prometheus: http://<vm-ip>:9090
Exporter:   http://<vm-ip>:9108/metrics
Gateway v2: http://<vm-ip>:13413/v2/owner
```

Grafana loads the `Grin Runtime` dashboard automatically.

## API v2

Owner endpoint for Rust Grin and Grin++:

```text
/v2/owner
Basic Auth: grin:node-test-owner-secret
```

Foreign secret is present beside each config as `.foreign_api_secret`.

## Metrics

The exporter currently publishes:

```text
grin_node_up
grin_node_height
grin_node_total_difficulty
grin_node_connections
grin_node_sync_status
grin_status_field_info
grin_peer_field_info
grin_peer_height
grin_peer_total_difficulty
```

## Logs / Warnings

The `monitor` service scans recent node logs for suspicious sync messages such as:

```text
Header batch cache full
throttling PIHD header segment request
BadHeader / BadBlockHeader
failed to send
try_send disconnected
PIHD/PIBD fallback or abort
```

## Clean Chain Data

```bash
docker compose down
sudo rm -rf nodes/gw/chain_data nodes/node-1/chain_data nodes/node-2/chain_data nodes/grinpp-node-1/FLOONET/NODE
```

To also reset Prometheus and Grafana state:

```bash
docker compose down -v
```

## Scale

Copy `nodes/node-2` to `nodes/node-3`, add a compose service, and update `GRIN_NODES`, `GRIN_INTERNAL_NODES`, `seeds`, and `peers_preferred`.
