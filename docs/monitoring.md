# Monitoring

Prometheus scrapes:

- `grin-exporter:9108`
- `runtime-controller:8080/metrics`
- `node-exporter:9100`
- `cadvisor:8080`

The exporter discovers node metadata from the Runtime Controller and exposes labels including node ID, node type, profile, experiment ID, image tag, commit hash, autosync state and failure state.

