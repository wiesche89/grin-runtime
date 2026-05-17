# Autosync

Autosync is stored per node in SQLite as `autosync_enabled`.

The scheduler polls node status, stores observations, detects completed sync runs and resets worker nodes when autosync is enabled. Reset means stop container, delete chain data/logs inside the node directory, and start the container again. For Grin++ the complete `FLOONET` runtime directory is removed and the generated config is recreated before restart.

Completion is detected by comparing worker height to gateway height. A worker is considered complete when it is API-up, has peers, and its current block height is within `RUNTIME_SYNC_COMPLETE_LAG` blocks of `grin-gw`.

The default lag is:

- `RUNTIME_SYNC_COMPLETE_LAG=2`

Supported endpoints:

- `POST /api/nodes/{node_id}/autosync/enable`
- `POST /api/nodes/{node_id}/autosync/disable`

Autosync actions are written to `action_log`. Each restart creates a new `sync_run_id` and benchmark row.

Grafana provisions `Grin Autosync Dashboard` for autosync state and sync-state monitoring.
