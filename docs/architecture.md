# Architecture

The runtime is split into a static control plane and dynamic worker plane.

The static compose file starts the gateway node, Runtime Controller, monitor, exporter, Prometheus, Grafana, node_exporter and cAdvisor. The generated compose file contains only worker Grin Rust and Grin++ nodes.

Grafana never executes shell commands. It reads Prometheus and controller data sources, and any write action must go through the Runtime Controller API.

