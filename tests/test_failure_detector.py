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


def test_active_sync_states_are_not_stuck_even_when_height_is_constant(monkeypatch):
    monkeypatch.setattr(failure_detector, "stuck_confirmation_observations", lambda: 3)
    observations = [
        {"container_running": 1, "api_up": 1, "peer_count": 2, "height": 0, "header_height": 100, "sync_state": "awaiting_peers"},
        {"container_running": 1, "api_up": 1, "peer_count": 2, "height": 0, "header_height": 100, "sync_state": "header_sync"},
        {"container_running": 1, "api_up": 1, "peer_count": 2, "height": 0, "header_height": 100, "sync_state": "txhashsetpibd_download"},
    ]

    assert not failure_detector.stuck_failure_confirmed(observations)


def test_io_activity_is_not_stuck_even_when_height_is_constant(monkeypatch):
    monkeypatch.setattr(failure_detector, "stuck_confirmation_observations", lambda: 3)
    observations = [
        {"container_running": 1, "api_up": 1, "peer_count": 2, "height": 0, "header_height": 100, "sync_state": "unknown", "disk_write_bytes": 30},
        {"container_running": 1, "api_up": 1, "peer_count": 2, "height": 0, "header_height": 100, "sync_state": "unknown", "disk_write_bytes": 20},
        {"container_running": 1, "api_up": 1, "peer_count": 2, "height": 0, "header_height": 100, "sync_state": "unknown", "disk_write_bytes": 10},
    ]

    assert not failure_detector.stuck_failure_confirmed(observations)


def test_no_peer_wait_is_not_stuck(monkeypatch):
    monkeypatch.setattr(failure_detector, "stuck_confirmation_observations", lambda: 3)
    observations = [
        {"container_running": 1, "api_up": 1, "peer_count": 0, "height": 0, "header_height": 0, "sync_state": "awaiting_peers"},
        {"container_running": 1, "api_up": 1, "peer_count": 0, "height": 0, "header_height": 0, "sync_state": "awaiting_peers"},
        {"container_running": 1, "api_up": 1, "peer_count": 0, "height": 0, "header_height": 0, "sync_state": "awaiting_peers"},
    ]

    assert not failure_detector.stuck_failure_confirmed(observations)


def test_inactive_node_can_be_stuck(monkeypatch):
    monkeypatch.setattr(failure_detector, "stuck_confirmation_observations", lambda: 3)
    observations = [
        {"container_running": 1, "api_up": 1, "peer_count": 2, "height": 10, "header_height": 20, "sync_state": "unknown", "disk_write_bytes": 10},
        {"container_running": 1, "api_up": 1, "peer_count": 2, "height": 10, "header_height": 20, "sync_state": "unknown", "disk_write_bytes": 10},
        {"container_running": 1, "api_up": 1, "peer_count": 2, "height": 10, "header_height": 20, "sync_state": "unknown", "disk_write_bytes": 10},
    ]

    assert failure_detector.stuck_failure_confirmed(observations)
