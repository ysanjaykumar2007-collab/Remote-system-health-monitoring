import socket
import json
import time
import os


MONITOR_IP = "10.0.0.1"
MONITOR_PORT = 5000
INTERVAL = 5


def get_cpu_usage():
    with open("/proc/stat", "r") as file:
        line = file.readline()

    values = line.split()[1:]
    total = sum(map(int, values))
    idle = int(values[3])

    return round((1 - (idle / total)) * 100, 2)


def get_memory_usage():
    memory_total = 0
    memory_available = 0

    with open("/proc/meminfo", "r") as file:
        for line in file:
            if line.startswith("MemTotal:"):
                memory_total = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                memory_available = int(line.split()[1])

    return round(
        ((memory_total - memory_available) / memory_total) * 100,
        2
    )


def get_process_count():
    return len(os.listdir("/proc"))


def get_network_stats():
    tx = 0
    rx = 0

    with open("/proc/net/dev", "r") as file:
        for line in file:
            if ":" not in line:
                continue

            interface, data = line.split(":", 1)

            if interface.strip() == "lo":
                continue

            values = data.split()

            rx += int(values[0])
            tx += int(values[8])

    return tx, rx


server_id = os.environ.get("SERVER_ID", "unknown")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"Health agent started for {server_id}")
print(f"Sending reports to {MONITOR_IP}:{MONITOR_PORT}")

while True:

    cpu = get_cpu_usage()
    memory = get_memory_usage()
    processes = get_process_count()
    network_tx, network_rx = get_network_stats()

    report = {
        "server_id": server_id,
        "cpu": cpu,
        "memory": memory,
        "processes": processes,
        "network_tx": network_tx,
        "network_rx": network_rx,
        "timestamp": time.time()
    }

    message = json.dumps(report).encode()

    sock.sendto(
        message,
        (MONITOR_IP, MONITOR_PORT)
    )

    print(f"Report sent: CPU={cpu}% Memory={memory}%")

    time.sleep(INTERVAL)
