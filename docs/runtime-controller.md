# Runtime Controller

The Runtime Controller is a FastAPI service in `controller/`.

It owns node lifecycle, SQLite registry writes, config generation, compose generation, Prometheus target generation, autosync flags, benchmark history, experiment metadata and failure state.

Write endpoints require `X-Runtime-Token`.

Implemented lifecycle endpoints:

- `GET /api/nodes`
- `POST /api/nodes`
- `DELETE /api/nodes/{node_id}`
- `POST /api/nodes/{node_id}/start`
- `POST /api/nodes/{node_id}/stop`
- `POST /api/nodes/{node_id}/restart`
- `POST /api/nodes/{node_id}/reset-chain`

