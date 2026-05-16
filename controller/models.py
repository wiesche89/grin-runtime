from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


NodeType = Literal["grin-rust", "grinpp", "gateway"]
NodeStatus = Literal["created", "starting", "running", "stopped", "deleted", "failed"]
FailureState = Literal["ok", "api_unreachable", "container_stopped", "stuck", "peerless", "resource_limit", "unknown"]


class NodeCreate(BaseModel):
    node_type: Literal["grin-rust", "grinpp"]
    profile: str = Field(default="default", pattern=r"^[a-zA-Z0-9_.-]{1,48}$")
    experiment_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_.-]{1,64}$")
    image_tag: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_.:-]{1,96}$")
    autosync_enabled: bool | None = None
    start: bool = True


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    node_profiles: list[dict] = Field(default_factory=list)
    autosync_enabled: bool = False
    labels: dict[str, str] = Field(default_factory=dict)


class NodeRecord(BaseModel):
    node_id: str
    node_name: str
    node_type: NodeType
    profile: str
    experiment_id: str | None = None
    container_name: str
    node_path: str
    api_port: int
    p2p_port: int
    metrics_port: int | None = None
    docker_image: str
    image_tag: str
    image_digest: str | None = None
    git_commit_hash: str | None = None
    build_date: str | None = None
    runtime_config_hash: str | None = None
    autosync_enabled: bool = False
    sync_state: str = "unknown"
    failure_state: FailureState = "unknown"
    status: NodeStatus = "created"
    sync_run_id: str | None = None
    last_sync_completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    last_action: str | None = None


class NodeActionResult(BaseModel):
    node: NodeRecord
    action: str
    dry_run: bool = False


class SystemHealth(BaseModel):
    status: str
    node_count: int
    running_node_count: int
    failures: int

