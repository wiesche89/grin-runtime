from controller.failure_detector import evaluate_node


def test_failure_detector_maps_stopped_container():
    assert evaluate_node({"status": "stopped"}) == "container_stopped"
    assert evaluate_node({"status": "running"}) == "ok"
