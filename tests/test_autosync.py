from controller.autosync_manager import should_reset_after_sync
from controller import autosync_manager


def test_autosync_requires_enabled_node_and_completed_sync(monkeypatch):
    monkeypatch.setattr(autosync_manager, "gateway_height", lambda: 100)
    monkeypatch.setattr(autosync_manager, "chain_validation_passed", lambda node: True)
    monkeypatch.setattr(
        autosync_manager.storage,
        "recent_observations",
        lambda node_id, limit: [
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 99},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 100},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 101},
        ],
    )
    node = {"autosync_enabled": True, "node_type": "grin-rust", "node_id": "node-1", "sync_run_id": "sync-1"}
    observation = {"api_up": 1, "container_running": 1, "peer_count": 3, "height": 99}

    assert should_reset_after_sync(node, "no_sync", observation)
    assert should_reset_after_sync(node, "synced", observation)
    assert should_reset_after_sync(node, "body_sync", {**observation, "height": 101})
    assert not should_reset_after_sync({"autosync_enabled": False, "node_type": "grin-rust"}, "synced", observation)


def test_autosync_rejects_lagging_or_invalid_observations(monkeypatch):
    node = {"autosync_enabled": True, "node_type": "grin-rust", "node_id": "node-1", "sync_run_id": "sync-1"}
    monkeypatch.setattr(autosync_manager, "gateway_height", lambda: 100)
    monkeypatch.setattr(autosync_manager, "chain_validation_passed", lambda node: True)
    monkeypatch.setattr(
        autosync_manager.storage,
        "recent_observations",
        lambda node_id, limit: [
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 90},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 91},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 92},
        ],
    )

    assert not should_reset_after_sync(node, "synced", {"api_up": 1, "container_running": 1, "peer_count": 3, "height": 90})
    assert not should_reset_after_sync(node, "synced", {"api_up": 0, "container_running": 1, "peer_count": 3, "height": 100})
    assert not should_reset_after_sync(node, "synced", {"api_up": 1, "container_running": 0, "peer_count": 3, "height": 100})
    assert not should_reset_after_sync(node, "synced", {"api_up": 1, "container_running": 1, "peer_count": 0, "height": 100})
    assert not should_reset_after_sync(node, "synced", {"api_up": 1, "container_running": 1, "peer_count": 3})


def test_autosync_requires_chain_validation_after_height_match(monkeypatch):
    node = {"autosync_enabled": True, "node_type": "grin-rust", "node_id": "node-1", "sync_run_id": "sync-1"}
    observation = {"api_up": 1, "container_running": 1, "peer_count": 3, "height": 100}
    monkeypatch.setattr(autosync_manager, "gateway_height", lambda: 100)
    monkeypatch.setattr(autosync_manager, "chain_validation_passed", lambda node: False)
    monkeypatch.setattr(
        autosync_manager.storage,
        "recent_observations",
        lambda node_id, limit: [
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 100},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 100},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 100},
        ],
    )

    assert not should_reset_after_sync(node, "no_sync", observation)


def test_grinpp_completion_does_not_call_validate_chain(monkeypatch):
    node = {"autosync_enabled": False, "node_type": "grinpp", "node_id": "grinpp-node-1", "sync_run_id": "sync-1"}
    observation = {"api_up": 1, "container_running": 1, "peer_count": 2, "height": 100, "sync_state": "no_sync"}
    monkeypatch.setattr(autosync_manager, "gateway_height", lambda: 100)
    monkeypatch.setattr(
        autosync_manager.storage,
        "recent_observations",
        lambda node_id, limit: [
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 2, "height": 100},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 2, "height": 100},
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 2, "height": 100},
        ],
    )
    monkeypatch.setattr(autosync_manager, "rpc", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("validate_chain called")))
    monkeypatch.setattr(autosync_manager.storage, "complete_benchmark_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(autosync_manager.storage, "update_node", lambda *args, **kwargs: None)

    autosync_manager.handle_sync_completion(node, observation)


def test_completed_sync_run_is_not_completed_again(monkeypatch):
    node = {
        "autosync_enabled": False,
        "node_type": "grin-rust",
        "node_id": "node-1",
        "sync_run_id": "sync-1",
        "last_sync_completed_at": "2026-05-18T10:00:00Z",
    }
    observation = {"api_up": 1, "container_running": 1, "peer_count": 2, "height": 100, "sync_state": "no_sync"}
    monkeypatch.setattr(autosync_manager, "is_sync_complete", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("is_sync_complete called")))

    autosync_manager.handle_sync_completion(node, observation)


def test_autosync_requires_multiple_confirmed_height_observations(monkeypatch):
    node = {"autosync_enabled": True, "node_type": "grin-rust", "node_id": "node-1", "sync_run_id": "sync-1"}
    observation = {"api_up": 1, "container_running": 1, "peer_count": 3, "height": 100}
    monkeypatch.setattr(autosync_manager, "gateway_height", lambda: 100)
    monkeypatch.setattr(autosync_manager, "chain_validation_passed", lambda node: True)
    monkeypatch.setattr(
        autosync_manager.storage,
        "recent_observations",
        lambda node_id, limit: [
            {"sync_run_id": "sync-1", "api_up": 1, "container_running": 1, "peer_count": 3, "height": 100},
        ],
    )

    assert not should_reset_after_sync(node, "no_sync", observation)
