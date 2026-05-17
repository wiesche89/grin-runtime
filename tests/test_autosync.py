from controller.autosync_manager import should_reset_after_sync
from controller import autosync_manager


def test_autosync_requires_enabled_node_and_completed_sync(monkeypatch):
    monkeypatch.setattr(autosync_manager, "gateway_height", lambda: 100)
    monkeypatch.setattr(autosync_manager, "benchmark_age_seconds", lambda node, sync_run_id: 300)
    monkeypatch.setattr(
        autosync_manager.storage,
        "recent_observations",
        lambda node_id, limit: [
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 99},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 100},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 98},
        ],
    )
    node = {"autosync_enabled": True, "node_type": "grin-rust", "node_id": "node-1", "sync_run_id": "sync-1"}
    observation = {"api_up": 1, "container_running": 1, "peer_count": 3, "height": 99}

    assert should_reset_after_sync(node, "no_sync", observation)
    assert should_reset_after_sync(node, "synced", observation)
    assert not should_reset_after_sync({"autosync_enabled": False, "node_type": "grin-rust"}, "synced", observation)


def test_autosync_rejects_young_or_lagging_runs(monkeypatch):
    node = {"autosync_enabled": True, "node_type": "grin-rust", "node_id": "node-1", "sync_run_id": "sync-1"}
    observation = {"api_up": 1, "container_running": 1, "peer_count": 3, "height": 99}
    monkeypatch.setattr(autosync_manager, "gateway_height", lambda: 100)
    monkeypatch.setattr(autosync_manager, "benchmark_age_seconds", lambda node, sync_run_id: 10)
    monkeypatch.setattr(
        autosync_manager.storage,
        "recent_observations",
        lambda node_id, limit: [
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 99},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 100},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 98},
        ],
    )

    assert not should_reset_after_sync(node, "synced", observation)

    monkeypatch.setattr(autosync_manager, "benchmark_age_seconds", lambda node, sync_run_id: 300)
    monkeypatch.setattr(
        autosync_manager.storage,
        "recent_observations",
        lambda node_id, limit: [
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 90},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 91},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 90},
        ],
    )

    assert not should_reset_after_sync(node, "synced", observation)
