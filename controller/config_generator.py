from __future__ import annotations

import json
from pathlib import Path

from .security import ensure_child_path
from .utils import NODES_DIR, sha256_text, write_json_if_changed, write_text_if_changed


PROFILES = {
    "gateway": {"peer_max_outbound_count": 12, "peer_min_preferred_outbound_count": 8, "archive_mode": False, "autosync_default": False, "chain_validation_mode": "Disabled"},
    "default": {"peer_max_outbound_count": 8, "peer_min_preferred_outbound_count": 2, "archive_mode": False, "autosync_default": False, "chain_validation_mode": "Disabled"},
    "low-memory": {"peer_max_outbound_count": 4, "peer_min_preferred_outbound_count": 1, "archive_mode": False, "autosync_default": False, "chain_validation_mode": "Disabled"},
    "high-peers": {"peer_max_outbound_count": 16, "peer_min_preferred_outbound_count": 6, "archive_mode": False, "autosync_default": False, "chain_validation_mode": "Disabled"},
    "pihd-test": {"peer_max_outbound_count": 8, "peer_min_preferred_outbound_count": 2, "archive_mode": False, "autosync_default": True, "chain_validation_mode": "Disabled"},
    "pibd-test": {"peer_max_outbound_count": 8, "peer_min_preferred_outbound_count": 2, "archive_mode": False, "autosync_default": True, "chain_validation_mode": "Disabled"},
    "archive": {"peer_max_outbound_count": 8, "peer_min_preferred_outbound_count": 2, "archive_mode": True, "autosync_default": False, "chain_validation_mode": "Disabled"},
    "pruned": {"peer_max_outbound_count": 8, "peer_min_preferred_outbound_count": 2, "archive_mode": False, "autosync_default": False, "chain_validation_mode": "Disabled"},
    "benchmark": {"peer_max_outbound_count": 8, "peer_min_preferred_outbound_count": 2, "archive_mode": False, "autosync_default": True, "chain_validation_mode": "Disabled"},
    "grinpp-compat": {"peer_max_outbound_count": 8, "peer_min_preferred_outbound_count": 2, "archive_mode": False, "autosync_default": False, "chain_validation_mode": "Disabled"},
    "validated": {"peer_max_outbound_count": 8, "peer_min_preferred_outbound_count": 2, "archive_mode": False, "autosync_default": False, "chain_validation_mode": "EveryBlock"},
}


def profile_config(profile: str) -> dict:
    if profile not in PROFILES:
        return PROFILES["default"]
    return PROFILES[profile]


def generate_rust_config(node_id: str, profile: str) -> tuple[Path, str]:
    cfg = profile_config(profile)
    node_dir = ensure_child_path(NODES_DIR, NODES_DIR / node_id)
    node_dir.mkdir(parents=True, exist_ok=True)
    peers = ['"grin-gw:13414"']
    content = f"""config_file_version = 2

[server]
db_root = "/root/.grin/test/chain_data"
api_http_addr = "0.0.0.0:13413"
api_secret_path = "/root/.grin/test/.api_secret"
foreign_api_secret_path = "/root/.grin/test/.foreign_api_secret"
chain_type = "Testnet"
future_time_limit = 300
chain_validation_mode = "{cfg['chain_validation_mode']}"
archive_mode = {str(bool(cfg["archive_mode"])).lower()}
skip_sync_wait = false
run_tui = false
run_test_miner = false

[server.p2p_config]
host = "0.0.0.0"
port = 13414
seeding_type = "List"
seeds = [{", ".join(peers)}]
peers_preferred = [{", ".join(peers)}]
peer_max_inbound_count = 32
peer_max_outbound_count = {cfg["peer_max_outbound_count"]}
peer_min_preferred_outbound_count = {cfg["peer_min_preferred_outbound_count"]}

[server.pool_config]
accept_fee_base = 500000
reorg_cache_period = 30
max_pool_size = 50000
max_stempool_size = 50000
mineable_max_weight = 40000

[server.dandelion_config]
epoch_secs = 600
embargo_secs = 180
aggregation_secs = 30
stem_probability = 90
always_stem_our_txs = true

[server.stratum_mining_config]
enable_stratum_server = false
stratum_server_addr = "127.0.0.1:13416"
attempt_time_per_block = 15
minimum_share_difficulty = 1
wallet_listener_url = "http://127.0.0.1:13415"
burn_reward = false

[server.webhook_config]
nthreads = 4
timeout = 10

[logging]
log_to_stdout = true
stdout_log_level = "Warning"
log_to_file = true
file_log_level = "Debug"
log_file_path = "/root/.grin/test/grin-server.log"
log_file_append = true
log_max_size = 16777216
log_max_files = 8
"""
    write_text_if_changed(node_dir / "grin-server.toml", content)
    write_text_if_changed(node_dir / ".api_secret", "node-test-owner-secret\n")
    write_text_if_changed(node_dir / ".foreign_api_secret", "node-test-foreign-secret\n")
    return node_dir, sha256_text(content)


def generate_grinpp_config(node_id: str, profile: str) -> tuple[Path, str]:
    cfg = profile_config(profile)
    node_dir = ensure_child_path(NODES_DIR, NODES_DIR / node_id)
    node_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "P2P": {
            "LISTEN_PORT": 13414,
            "P2P_PORT": 13414,
            "MAX_PEERS": max(8, int(cfg["peer_max_outbound_count"])),
            "MIN_PEERS": int(cfg["peer_min_preferred_outbound_count"]),
            "PREFERRED_PEERS": ["grin-gw:13414"],
        },
        "SERVER": {"REST_API_PORT": 13413},
        "WALLET": {"DATABASE": "SQLITE", "MIN_CONFIRMATIONS": 10},
    }
    write_json_if_changed(node_dir / "server_config.json", payload)
    floonet = node_dir / "FLOONET"
    floonet.mkdir(exist_ok=True)
    write_json_if_changed(floonet / "server_config.json", payload)
    return node_dir, sha256_text(json.dumps(payload, sort_keys=True))
