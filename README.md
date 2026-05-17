# Grin Runtime

Dynamic Grin node orchestration and benchmarking runtime.

The platform starts a static gateway node plus the monitoring/control plane. Additional Grin Rust and Grin++ worker nodes are created through the Runtime Controller API and are written into `compose/docker-compose.nodes.generated.yml`.

## Layout

- `compose/docker-compose.yml`: static gateway, controller, monitor, exporter, Prometheus, Grafana, node_exporter and cAdvisor.
- `compose/docker-compose.nodes.generated.yml`: generated worker nodes only.
- `controller/`: FastAPI Runtime Controller, SQLite registry, generators and orchestration managers.
- `nodes/`: gateway and generated node data/config directories.
- `monitoring/`: Prometheus, Grafana dashboards, datasources and alerts.
- `monitor/` and `exporter/`: dynamic node monitor and Prometheus exporter.
- `docs/`: architecture and operations notes.

## Run

```bash
./scripts/runtime-compose.sh
```

Initial services:

- `grin-gw`
- `runtime-controller`
- `monitor`
- `grin-exporter`
- `prometheus`
- `grafana`
- `node-exporter`
- `cadvisor`

No dynamic worker nodes start until they are created through the controller.

## Endpoints

```text
Grafana:             http://localhost:3000  admin / admin
Prometheus:          http://localhost:9090
Runtime Controller:  http://localhost:8080/api/system/health
Node Control UI:     http://localhost:8080/ui
Exporter:            http://localhost:9108/metrics
Gateway v2:          http://localhost:13413/v2/owner
```

Write operations can be protected with:

```text
X-Runtime-Token: <RUNTIME_CONTROLLER_TOKEN>
```

By default the local runtime starts without a write token. Set `RUNTIME_CONTROLLER_TOKEN` before running if you want write protection.

Grafana provisions a `Grin Node Control` dashboard with an embedded controller UI. If write auth is enabled, enter the runtime token once in the token field. If auth is disabled, the token field is hidden.

Grafana also provisions `Grin Runtime Operations` for dynamic host, container, node, autosync and failure-state monitoring.
Additional dashboards show benchmark history, experiments, autosync state and failure details.

When the controller runs Docker commands from inside its container, dynamic node bind mounts need the absolute host repository path. Start from the repository root with:

```bash
RUNTIME_DOCKER_HOST_ROOT=$PWD docker compose up --build
```

The helper script sets this automatically:

```bash
./scripts/runtime-compose.sh up -d --build
./scripts/runtime-compose.sh down
./scripts/runtime-compose.sh ps
```

For a clean runtime reset that preserves `nodes/gw` but removes dynamic workers and controller state:

```bash
./scripts/runtime-reset.sh
```

## Create Nodes

```bash
curl -X POST http://localhost:8080/api/nodes \
  -H "Content-Type: application/json" \
  -H "X-Runtime-Token: change-me" \
  -d '{"node_type":"grin-rust","profile":"pihd-test"}'

curl -X POST http://localhost:8080/api/nodes \
  -H "Content-Type: application/json" \
  -H "X-Runtime-Token: change-me" \
  -d '{"node_type":"grinpp","profile":"benchmark"}'
```

The controller allocates an ID, creates `nodes/<node_id>`, generates config, updates the generated compose file, updates Prometheus targets, persists metadata in SQLite and starts the container.

## Experiments

```bash
curl -X POST http://localhost:8080/api/experiments \
  -H "Content-Type: application/json" \
  -H "X-Runtime-Token: change-me" \
  -d '{"name":"PIHD comparison","node_profiles":[{"node_type":"grin-rust","profile":"pihd-test","count":3,"autosync_enabled":true},{"node_type":"grinpp","profile":"benchmark","count":3,"autosync_enabled":true}]}'
```

Start and stop experiments through:

```text
POST /api/experiments/{experiment_id}/start
POST /api/experiments/{experiment_id}/stop
```

## Tests

```bash
python -m pytest
```
