from controller import config_generator


def test_dynamic_rust_default_profile_disables_full_chain_validation(tmp_path, monkeypatch):
    nodes_dir = tmp_path / "nodes"
    monkeypatch.setattr(config_generator, "NODES_DIR", nodes_dir)

    node_dir, _config_hash = config_generator.generate_rust_config("node-1", "default")

    content = (node_dir / "grin-server.toml").read_text(encoding="utf-8")
    assert 'chain_validation_mode = "Disabled"' in content


def test_gateway_profile_can_remain_lightweight(tmp_path, monkeypatch):
    nodes_dir = tmp_path / "nodes"
    monkeypatch.setattr(config_generator, "NODES_DIR", nodes_dir)

    node_dir, _config_hash = config_generator.generate_rust_config("node-1", "gateway")

    content = (node_dir / "grin-server.toml").read_text(encoding="utf-8")
    assert 'chain_validation_mode = "Disabled"' in content


def test_validated_profile_opts_into_full_chain_validation(tmp_path, monkeypatch):
    nodes_dir = tmp_path / "nodes"
    monkeypatch.setattr(config_generator, "NODES_DIR", nodes_dir)

    node_dir, _config_hash = config_generator.generate_rust_config("node-1", "validated")

    content = (node_dir / "grin-server.toml").read_text(encoding="utf-8")
    assert 'chain_validation_mode = "EveryBlock"' in content
