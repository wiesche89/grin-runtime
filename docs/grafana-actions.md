# Grafana Actions

Grafana must call the Runtime Controller API for actions. It must not execute shell commands.

Supported action targets are the controller endpoints for node create, start, stop, restart, delete, reset chain and autosync enable/disable.

Use the controller API token in a secured Grafana data source or action plugin configuration. Do not hardcode shell commands in dashboards.
