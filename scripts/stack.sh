#!/bin/sh
# One command to stop or start everything: containers, Celery agents, API, frontend.
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"
log_dir="$repo_root/logs"
mkdir -p "$log_dir"

stop_dev_server() {
    pattern=$1
    pkill -f "$pattern" 2>/dev/null || true
}

start_dev_servers() {
    if ! pgrep -f "uvicorn cdm.backend.app:app" >/dev/null; then
        nohup uv run uvicorn cdm.backend.app:app --host 0.0.0.0 --port 8000 --reload \
            >> "$log_dir/backend-api.log" 2>&1 &
    fi
    if ! pgrep -f "frontend/app/node_modules/.bin/vite" >/dev/null; then
        nohup npm --prefix frontend/app run dev >> "$log_dir/frontend-dev.log" 2>&1 &
    fi
}

wait_for_port() {
    name=$1
    port=$2
    waited=0
    until nc -z localhost "$port" 2>/dev/null; do
        waited=$((waited + 2))
        if [ "$waited" -ge 180 ]; then
            printf 'Timed out waiting for %s on port %s\n' "$name" "$port" >&2
            return 1
        fi
        sleep 2
    done
}

down() {
    printf 'Stopping frontend and API...\n'
    stop_dev_server "frontend/app/node_modules/.bin/vite"
    stop_dev_server "npm --prefix frontend/app run dev"
    stop_dev_server "uvicorn cdm.backend.app:app"
    printf 'Stopping Celery agents...\n'
    sh scripts/ingest_launch_agent.sh stop
    printf 'Stopping containers (volumes preserved)...\n'
    make local-stop
    printf 'Everything is stopped.\n'
}

up() {
    make local
    printf 'Waiting for Elasticsearch, Redis, and RabbitMQ...\n'
    wait_for_port Elasticsearch 9200
    wait_for_port Redis 6379
    wait_for_port RabbitMQ 5672
    sh scripts/ingest_launch_agent.sh install
    start_dev_servers
    printf 'Up: frontend=http://localhost:5173 backend=http://localhost:8000\n'
}

status() {
    docker ps --format '{{.Names}}\t{{.Status}}' 2>/dev/null || printf 'docker not running\n'
    for label in ingest-recovery index maintenance beat; do
        if launchctl print "gui/$UID/com.congress-tracker.$label" >/dev/null 2>&1; then
            printf 'agent %s: loaded\n' "$label"
        else
            printf 'agent %s: not loaded\n' "$label"
        fi
    done
    pgrep -f "uvicorn cdm.backend.app:app" >/dev/null && printf 'backend: running\n' || printf 'backend: stopped\n'
    pgrep -f "frontend/app/node_modules/.bin/vite" >/dev/null && printf 'frontend: running\n' || printf 'frontend: stopped\n'
}

case "${1:-}" in
    up) up ;;
    down) down ;;
    restart) down; up ;;
    status) status ;;
    *)
        printf 'Usage: %s {up|down|restart|status}\n' "$0" >&2
        exit 2
        ;;
esac
