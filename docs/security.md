# Security

Safety rules enforced by the controller:

- write API operations require `X-Runtime-Token`
- node IDs are strictly validated
- profiles are validated
- filesystem deletion is constrained to `nodes/`
- subprocess calls use argument arrays
- `shell=True` is not used
- generated compose services are derived from registry data only
- gateway deletion is blocked

