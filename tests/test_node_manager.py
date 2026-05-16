from controller import node_manager


def test_next_node_number_considers_existing_node_directories(tmp_path, monkeypatch):
    nodes_dir = tmp_path / "nodes"
    nodes_dir.mkdir()
    (nodes_dir / "node-1").mkdir()
    (nodes_dir / "node-2").mkdir()
    monkeypatch.setattr(node_manager, "NODES_DIR", nodes_dir)
    monkeypatch.setattr(node_manager.storage, "list_nodes", lambda: [])

    assert node_manager.next_node_number("node-") == 3


def test_next_node_number_considers_existing_grinpp_directories(tmp_path, monkeypatch):
    nodes_dir = tmp_path / "nodes"
    nodes_dir.mkdir()
    (nodes_dir / "grinpp-node-1").mkdir()
    monkeypatch.setattr(node_manager, "NODES_DIR", nodes_dir)
    monkeypatch.setattr(node_manager.storage, "list_nodes", lambda: [])

    assert node_manager.next_node_number("grinpp-node-") == 2
