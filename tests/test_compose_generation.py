from controller.compose_generator import render_compose


def test_generated_compose_contains_only_dynamic_nodes():
    compose = render_compose(
        [
            {
                "node_id": "gw",
                "node_name": "grin-gw",
                "node_type": "gateway",
                "status": "running",
                "container_name": "grin-gw",
                "node_path": "nodes/gw",
                "docker_image": "grin-runtime",
                "image_tag": "staging",
                "profile": "gateway",
            },
            {
                "node_id": "node-1",
                "node_name": "node-1",
                "node_type": "grin-rust",
                "status": "created",
                "container_name": "node-1",
                "node_path": "nodes/node-1",
                "docker_image": "grin-runtime",
                "image_tag": "staging",
                "profile": "pihd-test",
            },
        ]
    )
    assert "grin-gw:" not in compose
    assert "node-1:" in compose
    assert "grin.node_id=node-1" in compose

