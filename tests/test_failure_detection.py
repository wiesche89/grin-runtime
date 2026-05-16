from controller.failure_detector import evaluate_node


def test_failure_detector_maps_stopped_container():
    assert evaluate_node({"status": "stopped"}) == "container_stopped"
    assert evaluate_node({"status": "running", "node_id": "node-1"}, [{"container_running": 1, "api_up": 1, "peer_count": 2, "height": 10}]) == "ok"
