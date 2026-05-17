from controller.autosync_manager import should_reset_after_sync
from controller import autosync_manager


def test_autosync_requires_enabled_node_and_completed_sync(monkeypatch):
    monkeypatch.setattr(autosync_manager, "gateway_height", lambda: 100)
    node = {"autosync_enabled": True, "node_type": "grin-rust"}
    observation = {"api_up": 1, "container_running": 1, "peer_count": 3, "height": 99}

    assert should_reset_after_sync(node, "no_sync", observation)
    assert should_reset_after_sync(node, "synced", observation)
    assert not should_reset_after_sync(node, "header_sync", {**observation, "height": 90})
    assert not should_reset_after_sync({"autosync_enabled": False, "node_type": "grin-rust"}, "synced", observation)
