#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
agent_dir="$HOME/Library/LaunchAgents"
log_dir="$repo_root/logs"

install_agent() {
    label=$1
    command=$2
    log_file=$3
    plist="$agent_dir/$label.plist"

    cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$label</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>-lc</string>
        <string>cd "$repo_root" &amp;&amp; exec "$uv_path" run celery $command</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$repo_root</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>30</integer>
    <key>ProcessType</key>
    <string>Background</string>
    <key>LowPriorityIO</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$log_dir/$log_file</string>
    <key>StandardErrorPath</key>
    <string>$log_dir/$log_file</string>
EOF
    if [ "$label" = "com.congress-tracker.ingest-recovery" ]; then
        cat >> "$plist" <<EOF
    <key>EnvironmentVariables</key>
    <dict>
        <key>CELERY_TASK_SOFT_TIME_LIMIT</key>
        <string>21600</string>
        <key>CELERY_TASK_TIME_LIMIT</key>
        <string>22200</string>
        <key>MONITOR</key>
        <string>0</string>
    </dict>
EOF
    fi
    cat >> "$plist" <<EOF
</dict>
</plist>
EOF

    launchctl bootout "gui/$UID/$label" 2>/dev/null || true
    launchctl bootstrap "gui/$UID" "$plist"
    launchctl kickstart -k "gui/$UID/$label"
}

usage() {
    printf 'Usage: %s {install|uninstall|status}\n' "$0"
}

case "${1:-}" in
    install)
        if [ "$(uname -s)" != "Darwin" ]; then
            printf 'This helper installs a macOS launch agent.\n' >&2
            exit 1
        fi
        uv_path=$(command -v uv || true)
        if [ -z "$uv_path" ]; then
            printf 'uv is required but was not found in PATH.\n' >&2
            exit 1
        fi

        mkdir -p "$agent_dir" "$log_dir"
        install_agent com.congress-tracker.ingest-recovery \
            '-A cdm.workers.celery_app:celery_app worker --hostname=ingest-launchd@%h --pool=prefork --concurrency=6 --max-tasks-per-child=10 --loglevel=INFO --queues=congress-ingest' \
            worker-ingest-launchd.log
        install_agent com.congress-tracker.index \
            '-A cdm.workers.celery_app:celery_app worker --hostname=index-launchd@%h --pool=prefork --concurrency=4 --max-tasks-per-child=1 --loglevel=INFO --queues=congress-index' \
            worker-index-launchd.log
        install_agent com.congress-tracker.beat \
            '-A cdm.workers.celery_app:celery_app beat --loglevel=INFO' \
            beat-launchd.log
        printf 'Installed and started supervised ingest, index, and beat agents.\n'
        ;;
    uninstall)
        for label in com.congress-tracker.ingest-recovery com.congress-tracker.index com.congress-tracker.beat; do
            launchctl bootout "gui/$UID/$label" 2>/dev/null || true
            rm -f "$agent_dir/$label.plist"
        done
        printf 'Uninstalled supervised Celery agents.\n'
        ;;
    status)
        for label in com.congress-tracker.ingest-recovery com.congress-tracker.index com.congress-tracker.beat; do
            printf '\n[%s]\n' "$label"
            launchctl print "gui/$UID/$label" 2>/dev/null || printf 'not loaded\n'
        done
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac