from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import Header, HTTPException, status


NODE_ID_RE = re.compile(r"^(gw|node-[0-9]{1,5}|grinpp-node-[0-9]{1,5})$")
PROFILE_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,48}$")


def validate_node_id(node_id: str) -> str:
    if not NODE_ID_RE.fullmatch(node_id):
        raise HTTPException(status_code=400, detail="invalid node_id")
    return node_id


def validate_profile(profile: str) -> str:
    if not PROFILE_RE.fullmatch(profile):
        raise HTTPException(status_code=400, detail="invalid profile")
    return profile


def require_write_token(x_runtime_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("RUNTIME_CONTROLLER_TOKEN", "")
    if not expected:
        return
    if x_runtime_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid runtime token")


def write_auth_required() -> bool:
    return bool(os.environ.get("RUNTIME_CONTROLLER_TOKEN", ""))


def ensure_child_path(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    if root_resolved != candidate_resolved and root_resolved not in candidate_resolved.parents:
        raise ValueError(f"path escapes allowed root: {candidate}")
    return candidate_resolved
