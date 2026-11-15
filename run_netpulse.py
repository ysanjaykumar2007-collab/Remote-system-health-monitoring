import os
import sys
import time
import signal
import subprocess
from pathlib import Path

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

PROJECT_DIR = Path(__file__).resolve().parent
net = None
processes = []


def start_host_process(host, command, log_name):
    log_path = PROJECT_DIR / log_name
    log_file = open(log_path, "w")

    process = host.popen(
        command,
        cwd=str(PROJECT_DIR),
        stdout=log_file,
        stderr=subprocess.STDOUT
    )

    log_file.close()
    processes.append(process)

    print(f"[NETPULSE] Started {host.name}: PID {process.pid}", flush=True)


def main():
    global net

    # Import our existing topology without modifying it.
    sys.path.insert(0, str(PROJECT_DIR))
    from topology import HealthMonitorTopo

    print("[NETPULSE] Creating Mininet network...", flush=True)

    net = Mininet(
        topo=HealthMonitorTopo(),
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True
    )

    net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6653
    )

    # Ensure the switch uses OpenFlow 1.3.
    for switch in net.switches:
        switch.cmd(
            "ovs-vsctl set bridge "
            f"{switch.name} protocols=OpenFlow13"
        )

    net.start()

    print("[NETPULSE] Waiting for controller connection...", flush=True)
    time.sleep(3)

    # Start monitoring server inside H1.
    h1 = net.get("h1")

    start_host_process(
        h1,
        ["python3", "-u", str(PROJECT_DIR / "monitor_server.py")],
        "monitor_server.log"
    )

    time.sleep(2)

    # Start agents inside H2-H5.
    for host_name in ["h2", "h3", "h4", "h5"]:
        host = net.get(host_name)

        command = [
            "env",
            f"SERVER_ID={host_name}",
            "python3",
            "-u",
            str(PROJECT_DIR / "health_agent.py")
        ]

        start_host_process(
            host,
            command,
            f"{host_name}_agent.log"
        )

    print("\n[NETPULSE] Network started successfully!", flush=True)
    print("[NETPULSE] Hosts: H1-H5", flush=True)
    print("[NETPULSE] Controller: 127.0.0.1:6653", flush=True)
    print("[NETPULSE] Monitoring server: UDP 5000", flush=True)
    print("[NETPULSE] Type 'exit' to stop Mininet.\n", flush=True)

    CLI(net)


def cleanup():
    print("\n[NETPULSE] Stopping health processes...", flush=True)

    for process in processes:
        if process.poll() is None:
            process.terminate()

    for process in processes:
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    # Stop any remaining project processes inside Mininet hosts.
    if net is not None:
        for host in net.hosts:
            host.cmd(
                "pkill -TERM -f '^python3 -u "
                + str(PROJECT_DIR / "monitor_server.py")
                + "$' || true"
            )
            host.cmd(
                "pkill -TERM -f '^python3 -u "
                + str(PROJECT_DIR / "health_agent.py")
                + "$' || true"
            )

        print("[NETPULSE] Stopping Mininet...", flush=True)
        net.stop()

if __name__ == "__main__":
    setLogLevel("info")

    try:
        main()
    finally:
        cleanup()
