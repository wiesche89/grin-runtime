# Monitoring

Prometheus scrapes:

- `grin-exporter:9108`
- `runtime-controller:8080/metrics`
- `node-exporter:9100`
- `cadvisor:8080`

The exporter discovers node metadata from the Runtime Controller and exposes labels including node ID, node type, profile, experiment ID, image tag, commit hash, autosync state and failure state.

The controller scheduler stores node observations and exposes them as `grin_runtime_node_observation` with a `metric` label. This includes API state, container state, height, peers, CPU, RAM, disk IO and network IO where Docker can provide the data.

Grafana provisions:

- `Grin Runtime`
- `Grin Node Control`
- `Grin Runtime Operations`

Prometheus and Grafana alert definitions cover node unreachable, peer count zero, stopped container and high CPU.
