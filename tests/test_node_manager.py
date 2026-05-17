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


def test_enforce_resource_limits_requires_absolute_host_root(monkeypatch):
    monkeypatch.setenv("RUNTIME_DOCKER_HOST_ROOT", "..")

    try:
        node_manager.enforce_resource_limits()
    except Exception as err:
        assert "RUNTIME_DOCKER_HOST_ROOT" in str(err)
    else:
        raise AssertionError("expected host root validation failure")


def test_reset_chain_removes_entire_grinpp_floonet_directory(tmp_path, monkeypatch):
    nodes_dir = tmp_path / "nodes"
    node_path = nodes_dir / "grinpp-node-1"
    stale_data = node_path / "FLOONET" / "NODE" / "chain.db"
    stale_log = node_path / "FLOONET" / "LOGS" / "Node.log"
    stale_data.parent.mkdir(parents=True)
    stale_log.parent.mkdir(parents=True)
    stale_data.write_text("chain", encoding="utf-8")
    stale_log.write_text("log", encoding="utf-8")
    monkeypatch.setattr(node_manager, "NODES_DIR", nodes_dir)
    monkeypatch.setattr(node_manager, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(node_manager, "compose_args", lambda *args: list(args))
    monkeypatch.setattr(node_manager, "run_command", lambda args, dry_run=False: None)
    monkeypatch.setattr(node_manager.storage, "get_node", lambda node_id: {
        "node_id": "grinpp-node-1",
        "node_name": "grinpp-node-1",
        "node_type": "grinpp",
        "profile": "default",
        "container_name": "grinpp-node-1",
        "node_path": "nodes/grinpp-node-1",
        "status": "running",
    })
    monkeypatch.setattr(node_manager.storage, "log_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(node_manager.storage, "start_benchmark_run", lambda *args, **kwargs: None)

    updated = {
        "node_id": "grinpp-node-1",
        "node_name": "grinpp-node-1",
        "node_type": "grinpp",
        "profile": "default",
    }
    monkeypatch.setattr(node_manager.storage, "update_node", lambda *args, **kwargs: updated)
    monkeypatch.setattr(node_manager.config_generator, "generate_grinpp_config", lambda node_id, profile: ((node_path), "hash"))

    node_manager.reset_chain("grinpp-node-1")

    assert not (node_path / "FLOONET").exists()
