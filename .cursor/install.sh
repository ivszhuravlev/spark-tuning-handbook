#!/usr/bin/env bash
# Idempotent setup for the Spark Tuning Handbook Cloud Agent environment.
#
# The Spark Standalone cluster (master + 2 workers) and the JupyterLab driver run
# entirely in Docker via docker-compose.yml, so the host only needs Docker Engine and
# the Compose plugin. All Spark/Python tooling lives inside the apache/spark image.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_IMAGE="apache/spark:4.0.2-python3"

install_docker() {
  if command -v docker >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1; then
    echo "[install] Docker Engine and Compose plugin already present."
    return
  fi
  echo "[install] Installing Docker Engine + Compose plugin..."
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io docker-compose-v2
}

prepull_image() {
  # Best-effort: pre-pull the Spark image so it is baked into the environment snapshot and
  # boots stay fast / independent of container egress. Uses a temporary dockerd that is
  # stopped again, because install must terminate and leave no lingering processes.
  command -v dockerd >/dev/null 2>&1 || return 0
  local started=0
  if ! sudo docker info >/dev/null 2>&1; then
    echo "[install] Starting temporary dockerd to pre-pull ${COMPOSE_IMAGE}..."
    sudo bash -c 'nohup dockerd >/tmp/dockerd-install.log 2>&1 &'
    started=1
    for _ in $(seq 1 30); do sudo docker info >/dev/null 2>&1 && break; sleep 1; done
  fi
  sudo docker pull "$COMPOSE_IMAGE" \
    || echo "[install] WARN: pre-pull failed; the image will be pulled on first start instead."
  if [ "$started" = "1" ]; then
    echo "[install] Stopping temporary dockerd."
    sudo pkill -TERM dockerd 2>/dev/null || true
    for _ in $(seq 1 15); do sudo docker info >/dev/null 2>&1 || break; sleep 1; done
  fi
}

install_docker
prepull_image
echo "[install] Done. Repo root: ${REPO_ROOT}"
