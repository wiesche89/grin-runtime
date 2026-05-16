# Grafana Actions

Grafana must call the Runtime Controller API for actions. It must not execute shell commands.

Supported action targets are the controller endpoints for node create, start, stop, restart, delete, reset chain and autosync enable/disable.

The current implementation provisions a `Grin Node Control` dashboard. It embeds the controller-hosted `/ui` page, which performs browser-side HTTPS requests to the Runtime Controller API with `X-Runtime-Token`.

The UI supports:

- Add Grin Rust node
- Add Grin++ node
- Start node
- Stop node
- Restart node
- Reset chain
- Delete worker node
- Enable autosync
- Disable autosync

The token is entered by the operator in the browser and stored in browser local storage. It is not hardcoded into the dashboard JSON.

If Grafana is accessed from another machine, open `http://<runtime-host>:8080/ui` directly or adjust the dashboard iframe URL to the externally reachable Runtime Controller URL.
