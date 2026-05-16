from pathlib import Path

import pytest

from controller.security import ensure_child_path, validate_node_id


def test_validate_node_id_accepts_known_runtime_ids():
    assert validate_node_id("gw") == "gw"
    assert validate_node_id("node-12") == "node-12"
    assert validate_node_id("grinpp-node-7") == "grinpp-node-7"


def test_validate_node_id_rejects_shell_and_path_values():
    with pytest.raises(Exception):
        validate_node_id("../node-1")
    with pytest.raises(Exception):
        validate_node_id("node-1;rm")


def test_ensure_child_path_blocks_escape(tmp_path: Path):
    root = tmp_path / "nodes"
    root.mkdir()
    child = root / "node-1" / "chain_data"
    child.parent.mkdir()
    assert ensure_child_path(root, child) == child.resolve()
    with pytest.raises(ValueError):
        ensure_child_path(root, tmp_path / "outside")

