# Experiments

Experiments group node profiles and benchmark labels. Starting an experiment creates the configured worker nodes dynamically and attaches `experiment_id` to each node and benchmark run.

Supported endpoints:

- `GET /api/experiments`
- `POST /api/experiments`
- `POST /api/experiments/{experiment_id}/start`
- `POST /api/experiments/{experiment_id}/stop`

Example `node_profiles` item:

```json
{"node_type":"grin-rust","profile":"pihd-test","count":3,"autosync_enabled":true}
```

Grafana provisions `Grin Experiments` for stored experiment metadata.
