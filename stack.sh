#!/usr/bin/env bash
# Start, stop and inspect the whole OCR platform on this machine with one command.
#
#   ./stack.sh up [--no-soup]   containers -> GPU servers -> supervisor -> frontend dev server
#   ./stack.sh down [--no-backup]  supervisor -> frontend -> backup snapshot -> containers -> GPU servers
#   ./stack.sh status           every part, plus the alerts Prometheus has firing
#
# Containers: backend/docker-compose.yml (project "ocr", settings in backend/.env). `up -d`, never `start`:
#   a container created before a secret rotation keeps the old secret (lesson of 30/09).
# GPU servers: backend/recognizer_server/manage.py on the host (decision D1), PID files in backend/data/run.
#   GPU_SERVERS below must match RECOGNIZER_URL / RECOGNIZER_ROUTES / LAYOUT_URL in backend/.env.
# Supervisor: `manage.py supervise` restarts a GPU server that dies, hangs or loses its GPU (CUDA error 999);
#   pid in backend/data/run/supervisor.json, log in backend/data/logs/supervisor.log, metrics on :8099.
# Backup: `down` takes a snapshot first (backend/tools/backup.py; only new page images are copied).
# Frontend: `npm run dev` on :8080 (or the PORT of frontend/.env.local) in its own process group; group id and
#   log in .run/.
#   Stopped by that group id, never by a pkill -f pattern (it would match the shell running it).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
RUN="$ROOT/.run"
MANAGE=(python3 "$BACKEND/recognizer_server/manage.py")
# 8080, unless frontend/.env.local moves the dev server (PORT=...): otherwise `up` would wait for the wrong port and
# report a failure, and `down` could miss a server it has no pgid file for.
FRONTEND_PORT=$(grep -oP '^PORT=\K[0-9]+' "$FRONTEND/.env.local" 2>/dev/null | tail -1 || true)
FRONTEND_PORT=${FRONTEND_PORT:-8080}

# port|manage.py arguments
GPU_SERVERS=(
  "8091|start-layout --port 8091"
  "8090|start-recognizer --model adapted --name paddleocr-vl-1.6-vbr-lr2e4-s3000 --port 8090"
  "8092|start-recognizer --model adapted --name paddleocr-vl-1.6-vbr-lr2e4-s3000 --port 8092"
  "8097|start-recognizer --model adapter:$ROOT/models/adapters/soup-r1r2 --name paddleocr-vl-1.6-vbr-soup-r1r2 --port 8097"
)
SOUP_PORT=8097

compose() { docker compose --project-directory "$BACKEND" -f "$BACKEND/docker-compose.yml" "$@"; }

supervisor_pid() {   # the running supervisor's pid, if any
  local f="$BACKEND/data/run/supervisor.json" pid
  [[ -f "$f" ]] || return 0
  pid=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["pid"])' "$f" 2>/dev/null || true)
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then echo "$pid"; fi
}

gpu_ready() {   # is a server on this port up and healthy?
  curl -sf -o /dev/null --max-time 3 "http://127.0.0.1:$1/health"
}

frontend_pgid() {   # the dev server's process group, from our file or from whoever listens on its port
  local pgid pid
  if [[ -f "$RUN/frontend.pgid" ]]; then
    pgid=$(<"$RUN/frontend.pgid")
    if kill -0 -- "-$pgid" 2>/dev/null; then echo "$pgid"; return; fi
    rm -f "$RUN/frontend.pgid"
  fi
  pid=$(ss -ltnpH "sport = :$FRONTEND_PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1 || true)
  [[ -n "$pid" && "$(readlink "/proc/$pid/cwd" 2>/dev/null)" == "$FRONTEND" ]] || return 0
  ps -o pgid= -p "$pid" | tr -d ' '
}

up() {
  local soup=1
  [[ "${1:-}" == "--no-soup" ]] && soup=0
  docker info >/dev/null 2>&1 || { echo "Docker is not running: start Docker Desktop first." >&2; exit 1; }
  mkdir -p "$RUN"

  echo "== containers"
  compose up -d --wait --wait-timeout 180

  echo "== GPU servers"
  local entry port args pids=() ports=() failed=0
  for entry in "${GPU_SERVERS[@]}"; do
    port=${entry%%|*}; args=${entry#*|}
    if [[ $port == "$SOUP_PORT" && $soup == 0 ]]; then echo ":$port skipped (--no-soup)"; continue; fi
    if gpu_ready "$port"; then echo ":$port already running"; continue; fi
    # shellcheck disable=SC2086  # args is a word list on purpose
    "${MANAGE[@]}" $args &
    pids+=($!); ports+=("$port")
  done
  for i in "${!pids[@]}"; do
    wait "${pids[$i]}" || { echo ":${ports[$i]} FAILED, see backend/data/logs/" >&2; failed=1; }
  done

  echo "== supervisor"
  if [[ -n "$(supervisor_pid)" ]]; then
    echo "already running (pid $(supervisor_pid))"
  else
    (setsid "${MANAGE[@]}" supervise >>"$BACKEND/data/logs/supervisor.out" 2>&1 </dev/null &) >/dev/null 2>&1 </dev/null
    sleep 1
    if [[ -n "$(supervisor_pid)" ]]; then echo "running (pid $(supervisor_pid))"; else echo "supervisor did not start" >&2; failed=1; fi
  fi

  echo "== frontend"
  if [[ -n "$(frontend_pgid)" ]]; then
    echo ":$FRONTEND_PORT already running"
  else
    # the subshell's own fds go to /dev/null too: otherwise it keeps a pipe from `./stack.sh up | tail` open
    (cd "$FRONTEND" && setsid bash -c "echo \$\$ > '$RUN/frontend.pgid'; exec npm run dev" \
      >"$RUN/frontend.log" 2>&1 </dev/null &) >/dev/null 2>&1 </dev/null
    local i
    for i in $(seq 90); do
      curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$FRONTEND_PORT/" && break
      sleep 1
    done
    if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$FRONTEND_PORT/"; then
      echo "frontend ready on :$FRONTEND_PORT"
    else
      echo "frontend not answering on :$FRONTEND_PORT after 90 s, see .run/frontend.log" >&2; failed=1
    fi
  fi
  echo
  status
  return $failed
}

down() {
  local backup=1
  [[ "${1:-}" == "--no-backup" ]] && backup=0
  echo "== supervisor"   # first, so it does not restart the servers being stopped
  local spid
  spid=$(supervisor_pid)
  if [[ -n "$spid" ]]; then
    kill -TERM "$spid"
    for i in $(seq 20); do kill -0 "$spid" 2>/dev/null || break; sleep 0.5; done
    if kill -0 "$spid" 2>/dev/null; then   # busy restarting a server: left alive it would start the servers stopped below again
      kill -KILL "$spid" 2>/dev/null || true
      echo "killed (pid $spid did not stop within 10 s)"
    else
      echo "stopped (pid $spid)"
    fi
  else
    echo "not running"
  fi

  echo "== frontend"
  local pgid i
  pgid=$(frontend_pgid)
  if [[ -n "$pgid" ]]; then
    kill -TERM -- "-$pgid" 2>/dev/null || true
    for i in $(seq 20); do kill -0 -- "-$pgid" 2>/dev/null || break; sleep 0.5; done
    kill -KILL -- "-$pgid" 2>/dev/null || true
    echo "stopped (process group $pgid)"
  else
    echo "not running"
  fi
  rm -f "$RUN/frontend.pgid"

  echo "== correction monitor"   # score new corrections into correction_stats while Postgres is still up
  if docker info >/dev/null 2>&1 && compose ps --status running --services 2>/dev/null | grep -qx postgres; then
    (cd "$BACKEND" && uv run --quiet python tools/correction_monitor.py) || echo "correction monitor FAILED" >&2
  else
    echo "skipped"
  fi

  echo "== backup"
  if [[ $backup == 1 ]] && docker info >/dev/null 2>&1 && compose ps --status running --services 2>/dev/null | grep -qx postgres; then
    python3 "$BACKEND/tools/backup.py" create || echo "backup FAILED: the stack is stopped anyway; run tools/backup.py create later" >&2
  else
    echo "skipped"
  fi

  echo "== containers"
  # `down` without -v: containers go, named volumes (Postgres, ValKey, Prometheus, Grafana) and data/storage stay.
  # Not `stop`: Docker Desktop loses the single-file bind mount (prometheus.yml) of a stopped container.
  if docker info >/dev/null 2>&1; then compose down; else echo "Docker is not running"; fi

  echo "== GPU servers"
  "${MANAGE[@]}" stop
}

status() {
  echo "== containers"
  if docker info >/dev/null 2>&1; then
    compose ps -a --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'
  else
    echo "Docker is not running"
  fi
  echo "== GPU servers"
  "${MANAGE[@]}" status
  echo "== frontend"
  local pgid
  pgid=$(frontend_pgid)
  if [[ -n "$pgid" ]]; then echo ":$FRONTEND_PORT running (process group $pgid)"; else echo "not running"; fi
  echo "== supervisor"
  if [[ -n "$(supervisor_pid)" ]]; then echo "running (pid $(supervisor_pid)), log backend/data/logs/supervisor.log"; else echo "not running"; fi
  echo "== alerts firing"
  curl -sf --max-time 3 http://127.0.0.1:9090/api/v1/alerts 2>/dev/null | python3 -c '
import json, sys
alerts = [a for a in json.load(sys.stdin)["data"]["alerts"] if a["state"] == "firing"]
for a in alerts:
    print(a["labels"]["alertname"], "-", a["annotations"].get("summary", ""))
print("none" if not alerts else "")' || echo "Prometheus not reachable"
  echo "== GPU memory"
  nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo "nvidia-smi unavailable"
}

case "${1:-}" in
  up) shift; up "$@" ;;
  down) shift; down "$@" ;;
  status) status ;;
  *) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
