#!/bin/bash
set -euo pipefail

# Stop the stack (or selected containers) using Podman.
#
# Usage:
#   ./scripts/stop.sh                # interactive (if TTY), otherwise podman-compose down
#   ./scripts/stop.sh --down         # podman-compose down (recommended)
#   ./scripts/stop.sh --list         # list matching containers
#   ./scripts/stop.sh --rm           # remove selected containers (podman rm -f)
#   MATCH_REGEX='piper' ./scripts/stop.sh --list

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DOWN=false
LIST=false
REMOVE=false

while [[ $# -gt 0 ]]; do
	case "$1" in
		--down)
			DOWN=true
			shift
			;;
		--list)
			LIST=true
			shift
			;;
		--rm)
			REMOVE=true
			shift
			;;
		*)
			echo "Unknown arg: $1" >&2
			echo "Usage: ./scripts/stop.sh [--down] [--list] [--rm]" >&2
			exit 2
			;;
	esac
done

MATCH_REGEX="${MATCH_REGEX:-piper-tts-capability}"

compose_down() {
	command -v podman-compose >/dev/null 2>&1 || { echo "podman-compose is required" >&2; exit 1; }
	podman-compose down
}

list_containers() {
	command -v podman >/dev/null 2>&1 || { echo "podman is required" >&2; exit 1; }
	podman ps --format '{{.ID}}\t{{.Names}}\t{{.Status}}' \
		| awk -v re="$MATCH_REGEX" '$2 ~ re {print}'
}

if $DOWN; then
	compose_down
	echo "OK"
	exit 0
fi

matches="$(list_containers || true)"
if [[ -z "$matches" ]]; then
	echo "No matching running containers (MATCH_REGEX=$MATCH_REGEX)."
	printf '%s\n' "Tip: list all containers with: podman ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
	exit 0
fi

if $LIST; then
	echo "$matches" | awk 'BEGIN{print "CONTAINER_ID\tNAME\tSTATUS"} {print}'
	exit 0
fi

# Default: if non-interactive, just compose down (most reliable way to stop the stack).
if [[ ! -t 0 ]]; then
	compose_down
	echo "OK"
	exit 0
fi

# Interactive selection.
mapfile -t rows < <(printf '%s\n' "$matches")

echo "Select a container to stop${REMOVE:+ (remove)}:"
for i in "${!rows[@]}"; do
	name="$(echo "${rows[$i]}" | awk '{print $2}')"
	status="$(echo "${rows[$i]}" | cut -f3- | sed 's/^\s*//')"
	printf '  [%d] %s\t%s\n' "$((i+1))" "$name" "$status"
done

echo "  [a] all matching containers"
echo "  [d] podman-compose down (recommended)"
echo "  [q] quit"

read -r -p "Choice: " choice

case "$choice" in
	q|Q)
		exit 0
		;;
	d|D)
		compose_down
		;;
	a|A)
		if $REMOVE; then
			printf '%s\n' "$matches" | awk '{print $2}' | xargs -r podman rm -f
		else
			printf '%s\n' "$matches" | awk '{print $2}' | xargs -r podman stop
		fi
		;;
	*)
		if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
			echo "Invalid choice." >&2
			exit 2
		fi
		idx=$((choice-1))
		if (( idx < 0 || idx >= ${#rows[@]} )); then
			echo "Invalid choice." >&2
			exit 2
		fi
		name="$(echo "${rows[$idx]}" | awk '{print $2}')"
		if $REMOVE; then
			podman rm -f "$name"
		else
			podman stop "$name"
		fi
		;;
esac

echo "OK"
