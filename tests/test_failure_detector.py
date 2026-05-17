from controller import failure_detector


def test_benchmark_failure_requires_confirmed_api_unreachable_observations():
    assert not failure_detector.benchmark_failure_confirmed("api_unreachable", [
        {"container_running": 1, "api_up": 0},
    ])
    assert failure_detector.benchmark_failure_confirmed("api_unreachable", [
        {"container_running": 1, "api_up": 0},
        {"container_running": 1, "api_up": 0},
        {"container_running": 1, "api_up": 0},
    ])


def test_benchmark_failure_rejects_transient_startup_api_state():
    assert not failure_detector.benchmark_failure_confirmed("api_unreachable", [
        {"container_running": 1, "api_up": 0},
        {"container_running": 1, "api_up": 1},
        {"container_running": 1, "api_up": 0},
    ])
