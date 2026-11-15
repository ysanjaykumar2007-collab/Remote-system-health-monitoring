#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROLLER_PID=""
DASHBOARD_PID=""

cleanup() {
    trap - EXIT INT TERM

    echo
    echo "[NETPULSE] Shutting down..."

    if [[ -n "$DASHBOARD_PID" ]]; then
        sudo kill "$DASHBOARD_PID" 2>/dev/null || true
        sudo pkill -P "$DASHBOARD_PID" 2>/dev/null || true
    fi

    if [[ -n "$CONTROLLER_PID" ]]; then
        kill "$CONTROLLER_PID" 2>/dev/null || true
    fi

    echo "[NETPULSE] Shutdown complete."
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cd "$PROJECT_DIR"

echo "=================================="
echo "       NETPULSE STARTUP"
echo "=================================="

# Ensure sudo authentication is available.
sudo -v

# Avoid overwriting an existing running network.
if sudo ovs-vsctl br-exists s1; then
    echo "[ERROR] Switch s1 already exists."
    echo "[ERROR] Stop the existing Mininet network before launching."
    exit 1
fi

# Avoid conflicting dashboard instances.
if sudo ss -ltn | grep -qE '127\.0\.0\.1:8080[[:space:]]'; then
    echo "[ERROR] Dashboard port 8080 is already in use."
    exit 1
fi

echo "[1/3] Starting SDN controller..."

OSKEN_HUB_TYPE=eventlet python3 -u start_controller.py \
    > controller.log 2>&1 &

CONTROLLER_PID=$!

sleep 3

if ! kill -0 "$CONTROLLER_PID" 2>/dev/null; then
    echo "[ERROR] Controller failed to start."
    echo "Check controller.log"
    exit 1
fi

echo "[2/3] Starting Mininet and monitoring services..."

# Dashboard starts after Mininet creates its switch interface.
(
    for attempt in $(seq 1 30); do
        if ip link show s1-eth1 >/dev/null 2>&1; then
            echo "[3/3] Starting dashboard..."

            exec sudo python3 -u \
                dashboard/dashboard_bridge.py \
                > dashboard.log 2>&1
        fi

        sleep 1
    done

    echo "[ERROR] Dashboard could not start: s1-eth1 not found."
) &

DASHBOARD_PID=$!

echo
echo "[NETPULSE] Launching network..."
echo "[NETPULSE] Dashboard: http://127.0.0.1:8080"
echo "[NETPULSE] Type exit at the Mininet prompt to shut down."
echo

sudo python3 -u run_netpulse.py
