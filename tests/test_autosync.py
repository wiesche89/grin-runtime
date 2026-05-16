from controller.autosync_manager import should_reset_after_sync


def test_autosync_requires_enabled_node_and_full_sync_state():
    node = {"autosync_enabled": True}
    assert should_reset_after_sync(node, "synced")
    assert should_reset_after_sync(node, "sync_finished")
    assert not should_reset_after_sync(node, "header_sync")
    assert not should_reset_after_sync({"autosync_enabled": False}, "synced")

