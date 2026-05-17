# Security

Safety rules enforced by the controller:

- write API operations require `X-Runtime-Token` only when `RUNTIME_CONTROLLER_TOKEN` is set
- node IDs are strictly validated
- profiles are validated
- filesystem deletion is constrained to `nodes/`
- subprocess calls use argument arrays
- `shell=True` is not used
- generated compose services are derived from registry data only
- gateway deletion is blocked
- worker creation is bounded by `RUNTIME_MAX_WORKER_NODES`
- worker creation can be blocked by `RUNTIME_MIN_FREE_DISK_GB`

For local lab usage the default compose stack leaves `RUNTIME_CONTROLLER_TOKEN` empty, so write actions are not token-protected. Set the variable for shared or exposed environments.
