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
docker compose up --build
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

Write operations require:

```text
X-Runtime-Token: change-me
```

Set `RUNTIME_CONTROLLER_TOKEN` before running for real usage.

Grafana provisions a `Grin Node Control` dashboard with an embedded controller UI. Enter the runtime token once in the token field, then use the buttons to add, start, stop, restart, reset, delete and toggle autosync for nodes. The token is stored in browser local storage only.

Grafana also provisions `Grin Runtime Operations` for dynamic host, container, node, autosync and failure-state monitoring.

When the controller runs Docker commands from inside its container, dynamic node bind mounts need the host repository path. If Docker cannot mount generated node directories, start with:

```bash
RUNTIME_DOCKER_HOST_ROOT=/absolute/path/to/grin-runtime docker compose up --build
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
