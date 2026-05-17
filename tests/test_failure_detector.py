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


def test_benchmark_failure_filters_observations_by_sync_run():
    observations = [
        {"sync_run_id": "new", "container_running": 1, "api_up": 1, "height": 0},
        {"sync_run_id": "old", "container_running": 1, "api_up": 1, "height": 0},
        {"sync_run_id": "old", "container_running": 1, "api_up": 1, "height": 0},
    ]

    assert failure_detector.observations_for_sync_run(observations, "new") == [observations[0]]
    assert not failure_detector.benchmark_failure_confirmed("stuck", failure_detector.observations_for_sync_run(observations, "new"))


def test_resource_limit_does_not_close_benchmark_as_failed():
    observations = [
        {"container_running": 1, "api_up": 1, "cpu_percent": 120},
        {"container_running": 1, "api_up": 1, "cpu_percent": 110},
        {"container_running": 1, "api_up": 1, "cpu_percent": 105},
    ]

    assert not failure_detector.benchmark_failure_confirmed("resource_limit", observations)
