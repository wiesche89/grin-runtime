# Autosync

Autosync is stored per node in SQLite as `autosync_enabled`.

The scheduler polls node status, stores observations, detects completed sync runs and resets worker nodes when autosync is enabled. Reset means stop container, delete chain data/logs inside the node directory, and start the container again. For Grin++ the complete `FLOONET` runtime directory is removed and the generated config is recreated before restart.

Completion is detected by comparing worker local block height to gateway local block height and validating the local chain through the owner API. The local block height is read from `sync_info.current_height`; `tip.height` is only a fallback when `sync_info.current_height` is unavailable. A worker is considered complete when it is API-up, has peers, the latest `RUNTIME_SYNC_COMPLETE_OBSERVATIONS` observations for the same `sync_run_id` are within `RUNTIME_SYNC_COMPLETE_LAG` blocks of `grin-gw`, and `validate_chain` succeeds.

The defaults are:

- `RUNTIME_SYNC_COMPLETE_OBSERVATIONS=3`
- `RUNTIME_SYNC_COMPLETE_LAG=2`

Supported endpoints:

- `POST /api/nodes/{node_id}/autosync/enable`
- `POST /api/nodes/{node_id}/autosync/disable`

Autosync actions are written to `action_log`. Each restart creates a new `sync_run_id` and benchmark row.

Grafana provisions `Grin Autosync Dashboard` for autosync state and sync-state monitoring.
