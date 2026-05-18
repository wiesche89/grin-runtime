from controller import node_manager


def test_refresh_generated_files_regenerates_existing_rust_configs(monkeypatch):
    nodes = [
        {
            "node_id": "node-5",
            "node_name": "node-5",
            "node_type": "grin-rust",
            "profile": "default",
            "status": "running",
            "runtime_config_hash": "old",
        }
    ]
    captured = {}

    monkeypatch.setattr(node_manager.storage, "list_nodes", lambda: nodes)
    monkeypatch.setattr(
        node_manager.config_generator,
        "generate_rust_config",
        lambda node_id, profile: (None, "new"),
    )
    monkeypatch.setattr(node_manager.compose_generator, "generate", lambda items: captured.setdefault("compose", items))
    monkeypatch.setattr(node_manager.monitoring_generator, "generate", lambda items: captured.setdefault("monitoring", items))
    monkeypatch.setattr(node_manager.storage, "update_node", lambda node_id, **kwargs: captured.setdefault("update", (node_id, kwargs)))

    node_manager.refresh_generated_files()

    assert captured["update"] == ("node-5", {"runtime_config_hash": "new"})
    assert captured["compose"] == nodes
    assert captured["monitoring"] == nodes


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


def test_reset_chain_clears_previous_completion_timestamp(tmp_path, monkeypatch):
    nodes_dir = tmp_path / "nodes"
    node_path = nodes_dir / "node-1"
    chain_data = node_path / "chain_data"
    chain_data.mkdir(parents=True)
    monkeypatch.setattr(node_manager, "NODES_DIR", nodes_dir)
    monkeypatch.setattr(node_manager, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(node_manager, "compose_args", lambda *args: list(args))
    monkeypatch.setattr(node_manager, "run_command", lambda args, dry_run=False: None)
    monkeypatch.setattr(node_manager.storage, "get_node", lambda node_id: {
        "node_id": "node-1",
        "node_name": "node-1",
        "node_type": "grin-rust",
        "profile": "default",
        "container_name": "node-1",
        "node_path": "nodes/node-1",
        "status": "running",
    })
    monkeypatch.setattr(node_manager.storage, "log_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(node_manager.storage, "start_benchmark_run", lambda *args, **kwargs: None)

    captured = {}

    def update_node(node_id, **kwargs):
        captured.update(kwargs)
        return {
            "node_id": node_id,
            "node_name": node_id,
            "node_type": "grin-rust",
            "profile": "default",
            **kwargs,
        }

    monkeypatch.setattr(node_manager.storage, "update_node", update_node)

    node_manager.reset_chain("node-1")

    assert captured["last_sync_completed_at"] is None
    assert captured["sync_run_id"].startswith("sync-")


def test_start_node_clears_previous_completion_timestamp(monkeypatch):
    monkeypatch.setattr(node_manager, "refresh_generated_files", lambda: None)
    monkeypatch.setattr(node_manager, "compose_args", lambda *args: list(args))
    monkeypatch.setattr(node_manager, "run_command", lambda args, dry_run=False: None)
    monkeypatch.setattr(node_manager.storage, "get_node", lambda node_id: {
        "node_id": "node-1",
        "node_name": "node-1",
        "node_type": "grin-rust",
        "profile": "default",
        "container_name": "node-1",
        "node_path": "nodes/node-1",
        "status": "stopped",
    })
    monkeypatch.setattr(node_manager.storage, "log_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(node_manager.storage, "start_benchmark_run", lambda *args, **kwargs: None)

    captured = {}

    def update_node(node_id, **kwargs):
        captured.update(kwargs)
        return {
            "node_id": node_id,
            "node_name": node_id,
            "node_type": "grin-rust",
            "profile": "default",
            **kwargs,
        }

    monkeypatch.setattr(node_manager.storage, "update_node", update_node)

    node_manager.start_node("node-1")

    assert captured["last_sync_completed_at"] is None
    assert captured["sync_run_id"].startswith("sync-")
