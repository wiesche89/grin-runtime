# Runtime Controller

The Runtime Controller is a FastAPI service in `controller/`.

It owns node lifecycle, SQLite registry writes, config generation, compose generation, Prometheus target generation, autosync flags, benchmark history, experiment metadata and failure state.

Write endpoints require `X-Runtime-Token`.

The controller also serves `/ui`, a small operator UI used by the Grafana `Grin Node Control` dashboard. The UI calls only the public controller API endpoints.

The background scheduler collects node observations, updates failure state, completes benchmark runs and executes autosync resets for worker nodes.

The controller also serves read-only dashboard pages:

- `/ui/benchmarks`
- `/ui/experiments`
- `/ui/failures`

Implemented lifecycle endpoints:

- `GET /api/nodes`
- `POST /api/nodes`
- `DELETE /api/nodes/{node_id}`
- `POST /api/nodes/{node_id}/start`
- `POST /api/nodes/{node_id}/stop`
- `POST /api/nodes/{node_id}/restart`
- `POST /api/nodes/{node_id}/reset-chain`

`DELETE /api/nodes/{node_id}?remove_files=true` stops and removes the worker container, removes the worker directory under `nodes/`, and regenerates dynamic compose/monitoring files. The Grafana control UI uses this mode for dynamic worker nodes so old chain data does not leak into recreated benchmark runs.
