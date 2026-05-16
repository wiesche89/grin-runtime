from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .utils import REPO_ROOT, utcnow_iso


DB_PATH = Path(__import__("os").environ.get("RUNTIME_DB_PATH", REPO_ROOT / "controller" / "runtime.db"))


NODE_COLUMNS = [
    "node_id", "node_name", "node_type", "profile", "experiment_id", "container_name", "node_path",
    "api_port", "p2p_port", "metrics_port", "docker_image", "image_tag", "image_digest",
    "git_commit_hash", "build_date", "runtime_config_hash", "autosync_enabled", "sync_state",
    "failure_state", "status", "sync_run_id", "last_sync_completed_at", "created_at", "updated_at",
    "last_action",
]


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            create table if not exists nodes (
              node_id text primary key,
              node_name text not null,
              node_type text not null,
              profile text not null,
              experiment_id text,
              container_name text not null,
              node_path text not null,
              api_port integer not null,
              p2p_port integer not null,
              metrics_port integer,
              docker_image text not null,
              image_tag text not null,
              image_digest text,
              git_commit_hash text,
              build_date text,
              runtime_config_hash text,
              autosync_enabled integer not null default 0,
              sync_state text not null default 'unknown',
              failure_state text not null default 'unknown',
              status text not null default 'created',
              sync_run_id text,
              last_sync_completed_at text,
              created_at text not null,
              updated_at text not null,
              last_action text
            );
            create table if not exists benchmark_runs (
              id integer primary key autoincrement,
              node_id text not null,
              node_name text not null,
              node_type text not null,
              profile text not null,
              experiment_id text,
              docker_image text,
              image_tag text,
              git_commit_hash text,
              sync_run_id text,
              sync_started_at text,
              sync_completed_at text,
              total_sync_duration real,
              header_sync_duration real,
              PIHD_duration real,
              PIBD_duration real,
              rangeproof_validation_duration real,
              kernel_validation_duration real,
              final_height integer,
              average_peer_count real,
              max_cpu_usage real,
              max_ram_usage real,
              max_disk_io real,
              result text,
              error_message text
            );
            create table if not exists node_observations (
              id integer primary key autoincrement,
              node_id text not null,
              observed_at text not null,
              api_up integer not null,
              container_running integer not null,
              sync_state text,
              height integer,
              header_height integer,
              peer_count integer,
              cpu_percent real,
              ram_bytes integer,
              disk_read_bytes integer,
              disk_write_bytes integer,
              network_rx_bytes integer,
              network_tx_bytes integer,
              error_message text
            );
            create table if not exists experiments (
              experiment_id text primary key,
              experiment_name text not null,
              description text,
              node_profiles_json text not null default '[]',
              labels_json text not null default '{}',
              created_at text not null,
              started_at text,
              stopped_at text,
              status text not null
            );
            create table if not exists action_log (
              id integer primary key autoincrement,
              created_at text not null,
              node_id text,
              action text not null,
              detail text
            );
            """
        )
        ensure_column(conn, "experiments", "node_profiles_json", "text not null default '[]'")
        ensure_gateway(conn)


def ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {row["name"] for row in conn.execute(f"pragma table_info({table})")}
    if column not in columns:
        conn.execute(f"alter table {table} add column {column} {ddl}")


def ensure_gateway(conn: sqlite3.Connection) -> None:
    now = utcnow_iso()
    conn.execute(
        """
        insert into nodes (
          node_id, node_name, node_type, profile, container_name, node_path, api_port, p2p_port,
          metrics_port, docker_image, image_tag, autosync_enabled, sync_state, failure_state, status,
          created_at, updated_at, last_action
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(node_id) do nothing
        """,
        (
            "gw", "grin-gw", "gateway", "gateway", "grin-gw", "nodes/gw", 13413, 13414,
            None, "grin-runtime", "staging", 0, "unknown", "unknown", "running", now, now, "bootstrap",
        ),
    )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["autosync_enabled"] = bool(data.get("autosync_enabled"))
    return data


def list_nodes() -> list[dict[str, Any]]:
    with connect() as conn:
        return [row_to_dict(row) for row in conn.execute("select * from nodes where status != 'deleted' order by node_id")]


def get_node(node_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        return row_to_dict(conn.execute("select * from nodes where node_id = ?", (node_id,)).fetchone())


def insert_node(data: dict[str, Any]) -> None:
    with connect() as conn:
        values = [int(data[c]) if c == "autosync_enabled" else data.get(c) for c in NODE_COLUMNS]
        conn.execute(
            f"insert into nodes ({', '.join(NODE_COLUMNS)}) values ({', '.join('?' for _ in NODE_COLUMNS)})",
            values,
        )


def update_node(node_id: str, **fields: Any) -> dict[str, Any]:
    if not fields:
        node = get_node(node_id)
        if node is None:
            raise KeyError(node_id)
        return node
    fields["updated_at"] = utcnow_iso()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = [int(value) if key == "autosync_enabled" else value for key, value in fields.items()]
    with connect() as conn:
        conn.execute(f"update nodes set {assignments} where node_id = ?", [*values, node_id])
    node = get_node(node_id)
    if node is None:
        raise KeyError(node_id)
    return node


def delete_node(node_id: str) -> None:
    update_node(node_id, status="deleted", last_action="delete")


def log_action(action: str, node_id: str | None = None, detail: str = "") -> None:
    with connect() as conn:
        conn.execute(
            "insert into action_log (created_at, node_id, action, detail) values (?, ?, ?, ?)",
            (utcnow_iso(), node_id, action, detail),
        )


def list_benchmarks() -> list[dict[str, Any]]:
    with connect() as conn:
        return [dict(row) for row in conn.execute("select * from benchmark_runs order by id desc limit 500")]


def insert_observation(node_id: str, data: dict[str, Any]) -> None:
    columns = [
        "node_id", "observed_at", "api_up", "container_running", "sync_state", "height", "header_height",
        "peer_count", "cpu_percent", "ram_bytes", "disk_read_bytes", "disk_write_bytes",
        "network_rx_bytes", "network_tx_bytes", "error_message",
    ]
    payload = {"node_id": node_id, "observed_at": utcnow_iso(), **data}
    with connect() as conn:
        conn.execute(
            f"insert into node_observations ({', '.join(columns)}) values ({', '.join('?' for _ in columns)})",
            [payload.get(column) for column in columns],
        )


def latest_observation(node_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        return row_to_dict(
            conn.execute(
                "select * from node_observations where node_id = ? order by id desc limit 1",
                (node_id,),
            ).fetchone()
        )


def recent_observations(node_id: str, limit: int = 12) -> list[dict[str, Any]]:
    with connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                "select * from node_observations where node_id = ? order by id desc limit ?",
                (node_id, limit),
            )
        ]


def start_benchmark_run(node: dict[str, Any], sync_run_id: str) -> None:
    with connect() as conn:
        exists = conn.execute(
            "select id from benchmark_runs where node_id = ? and sync_run_id = ?",
            (node["node_id"], sync_run_id),
        ).fetchone()
        if exists:
            return
        conn.execute(
            """
            insert into benchmark_runs (
              node_id, node_name, node_type, profile, experiment_id, docker_image, image_tag,
              git_commit_hash, sync_run_id, sync_started_at, result
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node["node_id"], node["node_name"], node["node_type"], node["profile"], node.get("experiment_id"),
                node.get("docker_image"), node.get("image_tag"), node.get("git_commit_hash"), sync_run_id,
                utcnow_iso(), "running",
            ),
        )


def complete_benchmark_run(node: dict[str, Any], sync_run_id: str, final_height: int | None, result: str = "success", error_message: str | None = None) -> None:
    with connect() as conn:
        row = conn.execute(
            "select sync_started_at from benchmark_runs where node_id = ? and sync_run_id = ?",
            (node["node_id"], sync_run_id),
        ).fetchone()
        completed = utcnow_iso()
        duration = None
        if row and row["sync_started_at"]:
            from datetime import datetime

            started = datetime.fromisoformat(row["sync_started_at"])
            ended = datetime.fromisoformat(completed)
            duration = max(0.0, (ended - started).total_seconds())
        stats = conn.execute(
            """
            select avg(peer_count) as average_peer_count, max(cpu_percent) as max_cpu_usage,
                   max(ram_bytes) as max_ram_usage, max(coalesce(disk_read_bytes, 0) + coalesce(disk_write_bytes, 0)) as max_disk_io
            from node_observations where node_id = ?
            """,
            (node["node_id"],),
        ).fetchone()
        conn.execute(
            """
            update benchmark_runs
            set sync_completed_at = ?, total_sync_duration = ?, final_height = ?,
                average_peer_count = ?, max_cpu_usage = ?, max_ram_usage = ?, max_disk_io = ?,
                result = ?, error_message = ?
            where node_id = ? and sync_run_id = ?
            """,
            (
                completed, duration, final_height, stats["average_peer_count"], stats["max_cpu_usage"],
                stats["max_ram_usage"], stats["max_disk_io"], result, error_message,
                node["node_id"], sync_run_id,
            ),
        )


def list_experiments() -> list[dict[str, Any]]:
    with connect() as conn:
        return [dict(row) for row in conn.execute("select * from experiments order by created_at desc")]


def insert_experiment(experiment_id: str, name: str, description: str, labels_json: str, node_profiles_json: str = "[]") -> dict[str, Any]:
    now = utcnow_iso()
    with connect() as conn:
        conn.execute(
            """
            insert into experiments (experiment_id, experiment_name, description, node_profiles_json, labels_json, created_at, status)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (experiment_id, name, description, node_profiles_json, labels_json, now, "created"),
        )
    return {
        "experiment_id": experiment_id,
        "experiment_name": name,
        "description": description,
        "node_profiles_json": node_profiles_json,
        "labels_json": labels_json,
        "created_at": now,
        "status": "created",
    }


def get_experiment(experiment_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        return row_to_dict(conn.execute("select * from experiments where experiment_id = ?", (experiment_id,)).fetchone())


def update_experiment(experiment_id: str, **fields: Any) -> dict[str, Any]:
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with connect() as conn:
        conn.execute(f"update experiments set {assignments} where experiment_id = ?", [*fields.values(), experiment_id])
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise KeyError(experiment_id)
    return experiment


def list_nodes_for_experiment(experiment_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        return [
            row_to_dict(row)
            for row in conn.execute(
                "select * from nodes where experiment_id = ? and status != 'deleted' order by node_id",
                (experiment_id,),
            )
        ]
