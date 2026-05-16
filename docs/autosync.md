# Autosync

Autosync is stored per node in SQLite as `autosync_enabled`.

The first implementation includes persistent API controls and the reset decision logic. A synced node with autosync enabled is eligible for stop, chain deletion and restart from scratch.

Supported endpoints:

- `POST /api/nodes/{node_id}/autosync/enable`
- `POST /api/nodes/{node_id}/autosync/disable`

