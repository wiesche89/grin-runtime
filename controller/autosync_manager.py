from __future__ import annotations

from . import storage


FULL_SYNC_STATES = {"no_sync", "synced", "sync_finished"}


def should_reset_after_sync(node: dict, latest_sync_state: str) -> bool:
    return bool(node.get("autosync_enabled")) and latest_sync_state in FULL_SYNC_STATES


def set_autosync(node_id: str, enabled: bool) -> dict:
    return storage.update_node(node_id, autosync_enabled=enabled, last_action="autosync_enable" if enabled else "autosync_disable")

