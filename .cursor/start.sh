#!/usr/bin/env bash
# Per-boot startup for the Spark Tuning Handbook Cloud Agent environment.
#
# Starts the Docker daemon, applies the Docker-in-Docker networking fixes required in the
# Cloud Agent VM, and brings up the Spark Standalone cluster + JupyterLab defined in
# docker-compose.yml. Returns once the cluster reports 2 alive workers and JupyterLab is up.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE=(sudo docker compose -f "${REPO_ROOT}/docker-compose.yml")

DOCKERD_LOG=/tmp/spark-handbook-dockerd.log

start_dockerd() {
  if sudo docker info >/dev/null 2>&1; then
    echo "[start] dockerd already running."
    return
  fi
  echo "[start] Starting dockerd..."
  # A snapshot or prior boot can leave a stale pidfile (dockerd then refuses to start) and a
  # log file at a fixed path that the redirect cannot reopen. Clear both first (root removes
  # regardless of owner) so startup is robust across reboots and prebuilt-snapshot boots.
  sudo rm -f /var/run/docker.pid "$DOCKERD_LOG" 2>/dev/null || true
  sudo bash -c "nohup dockerd >'$DOCKERD_LOG' 2>&1 &"
  for _ in $(seq 1 60); do
    sudo docker info >/dev/null 2>&1 && { echo "[start] dockerd is up."; return; }
    sleep 1
  done
  echo "[start] ERROR: dockerd did not become ready." >&2
  sudo tail -n 40 "$DOCKERD_LOG" >&2 2>/dev/null || true
  exit 1
}

fix_networking() {
  # Docker-in-Docker: same-host container traffic and outbound NAT are blocked by the stale
  # legacy iptables FORWARD chain (policy DROP), which Docker's nft backend does not manage,
  # and by bridge netfilter routing bridged frames through iptables. Let bridged traffic
  # bypass iptables and accept forwarding on the legacy chain so worker->master registration
  # and container egress (Jupyter's `pip install jupyterlab`) both work.
  sudo sysctl -w net.bridge.bridge-nf-call-iptables=0  >/dev/null 2>&1 || true
  sudo sysctl -w net.bridge.bridge-nf-call-ip6tables=0 >/dev/null 2>&1 || true
  if command -v iptables-legacy >/dev/null 2>&1; then
    sudo iptables-legacy -P FORWARD ACCEPT 2>/dev/null || true
  fi
}

wait_http() {
  local url="$1" name="$2" tries="${3:-60}" code
  for _ in $(seq 1 "$tries"); do
    code=$(curl -sS -m 5 -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo 000)
    case "$code" in 2*|3*) echo "[start] ${name} ready (HTTP ${code})."; return 0 ;; esac
    sleep 2
  done
  echo "[start] WARN: ${name} not ready at ${url}." >&2
  return 1
}

alive_workers() {
  local n
  n=$(curl -sS -m 5 http://localhost:8080/json/ 2>/dev/null \
      | tr ',' '\n' | grep -i aliveworkers | grep -o '[0-9]\+' | head -1 || true)
  echo "${n:-0}"
}

start_dockerd
fix_networking

echo "[start] Bringing up Spark cluster + JupyterLab..."
"${COMPOSE[@]}" up -d

wait_http "http://localhost:8080/" "Spark Master UI" 60 || true

# Ensure both workers register. The networking fix above is in place before compose up, but
# restart workers once as a safety net in case they hit their connection backoff first.
ok=0
for attempt in 1 2; do
  for _ in $(seq 1 30); do
    [ "$(alive_workers)" = "2" ] && { ok=1; break; }
    sleep 2
  done
  [ "$ok" = "1" ] && break
  echo "[start] Only $(alive_workers)/2 workers registered; restarting workers (attempt ${attempt})..."
  "${COMPOSE[@]}" restart spark-worker-1 spark-worker-2
done

if [ "$ok" != "1" ]; then
  echo "[start] ERROR: Spark workers did not register with the master." >&2
  exit 1
fi
echo "[start] Spark cluster healthy: 2 workers registered (4 cores, 4 GiB total)."

# JupyterLab installs jupyterlab inside its container on first start, then launches; allow time.
wait_http "http://localhost:8888/api" "JupyterLab" 120 \
  || { echo "[start] ERROR: JupyterLab did not become ready." >&2; exit 1; }

cat <<'EOF'
[start] Environment ready:
  JupyterLab       -> http://localhost:8888/lab   (no token/password)
  Spark Master UI  -> http://localhost:8080
  Spark Worker 1   -> http://localhost:8081
  Spark Worker 2   -> http://localhost:8082
  Spark Application-> http://localhost:4040        (after a notebook/app starts)
EOF
