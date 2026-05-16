from __future__ import annotations

import hashlib
import json
import os
import shutil
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(os.environ.get("RUNTIME_REPO_ROOT", Path(__file__).resolve().parents[1])).resolve()
COMPOSE_DIR = REPO_ROOT / "compose"
NODES_DIR = REPO_ROOT / "nodes"
PROM_TARGETS_DIR = REPO_ROOT / "monitoring" / "prometheus" / "targets"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_text_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def write_json_if_changed(path: Path, payload: object) -> None:
    write_text_if_changed(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def run_command(args: Sequence[str], *, dry_run: bool = False, timeout: int = 120) -> subprocess.CompletedProcess[str] | None:
    if dry_run:
        return None
    return subprocess.run(
        list(args),
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def compose_args(*extra: str) -> list[str]:
    base = shlex.split(os.environ.get("RUNTIME_COMPOSE_COMMAND", "docker compose"))
    return [
        *base,
        "-f",
        str(COMPOSE_DIR / "docker-compose.yml"),
        "-f",
        str(COMPOSE_DIR / "docker-compose.nodes.generated.yml"),
        *extra,
    ]
