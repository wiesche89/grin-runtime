#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

export RUNTIME_DOCKER_HOST_ROOT="${RUNTIME_DOCKER_HOST_ROOT:-$REPO_ROOT}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-grin-runtime}"

cd "$REPO_ROOT"

if [ "$#" -eq 0 ]; then
  set -- up -d --build
fi

exec docker compose "$@"

