#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

case "${1:-}" in
    up) exec make stack-up ;;
    down) exec make stack-down ;;
    restart) make stack-down; exec make stack-up ;;
    status) exec make stack-status ;;
    check)
        if [ "$(uname -s)" = Darwin ]; then
            for name in ingest-recovery index maintenance beat; do
                label="com.congress-tracker.$name"
                if [ -e "$HOME/Library/LaunchAgents/$label.plist" ] ||
                    launchctl print "gui/$(id -u)/$label" >/dev/null 2>&1; then
                    printf 'Legacy agent %s must be retired before Compose startup. See documentation/OPERATIONS_RUNBOOK.md.\n' "$label" >&2
                    exit 1
                fi
            done
        fi
        ;;
    *) printf 'Usage: %s {up|down|restart|status|check}\n' "$0" >&2; exit 2 ;;
esac
