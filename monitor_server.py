import socket
import json
import time
import threading

HOST = "0.0.0.0"
PORT = 5000

CPU_WARNING = 80
CPU_CRITICAL = 90

MEMORY_WARNING = 80
MEMORY_CRITICAL = 90

SERVER_TIMEOUT = 15
SDN_SOCKET = "/tmp/netpulse-control.sock"

last_seen = {}
blocked_hosts = set()

# Map monitoring agent IDs to their Mininet IP addresses.
HOST_IPS = {
    "h2": "10.0.0.2",
    "h3": "10.0.0.3",
    "h4": "10.0.0.4",
    "h5": "10.0.0.5"
}


def send_sdn_command(action, server_id):
    """Request a blocking or unblocking action from the SDN controller."""

    host_ip = HOST_IPS.get(server_id)

    if host_ip is None:
        print(f"[SDN] Unknown server: {server_id}")
        return False

    command = {
        "action": action,
        "host_ip": host_ip
    }

    try:
        with socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM
        ) as client:

            client.settimeout(3)
            client.connect(SDN_SOCKET)
            client.sendall(json.dumps(command).encode())

            response = client.recv(1024).decode()

        if response == "OK":
            print(f"[SDN] {action.upper()} successful: {server_id}")
            return True

        print(f"[SDN] Controller rejected command: {response}")
        return False

    except (OSError, socket.timeout) as error:
        print(f"[SDN] Controller communication failed: {error}")
        return False


def update_sdn_state(server_id, cpu, memory):
    """Block critical hosts and unblock recovered hosts."""

    critical = cpu >= CPU_CRITICAL or memory >= MEMORY_CRITICAL

    if critical:
        # Reconcile automatic blocking after controller restarts.
        if server_id not in blocked_hosts:
            print(f"[SDN] Critical condition detected on {server_id}")

        if send_sdn_command("block", server_id):
            blocked_hosts.add(server_id)

    elif not critical:
        # Reconcile automatic blocking state after server restarts.
        # Manual blocks remain protected by the controller.
        if send_sdn_command("unblock", server_id):
            blocked_hosts.discard(server_id)


def check_missing_servers():
    while True:
        current_time = time.time()

        for server_id, last_time in list(last_seen.items()):
            if current_time - last_time > SERVER_TIMEOUT:
                print(
                    f"!!! FAILURE ALERT: {server_id} "
                    f"has not sent a report for "
                    f"{int(current_time - last_time)} seconds !!!"
                )

        time.sleep(2)


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))

print("Health Monitoring Server started")
print(f"Listening for UDP health reports on port {PORT}...")
print("Alert monitoring enabled")
print("Dynamic SDN control enabled")

threading.Thread(
    target=check_missing_servers,
    daemon=True
).start()


while True:
    data, address = sock.recvfrom(4096)

    try:
        report = json.loads(data.decode())

        server_id = report["server_id"]
        cpu = report["cpu"]
        memory = report["memory"]

        current_time = time.time()
        last_seen[server_id] = current_time

        print("\n--- Health Report ---")
        print(f"From       : {address[0]}")
        print(f"Server ID  : {server_id}")
        print(f"CPU        : {cpu}%")
        print(f"Memory     : {memory}%")
        print(f"Processes  : {report['processes']}")
        print(f"Network TX : {report['network_tx']}")
        print(f"Network RX : {report['network_rx']}")
        print(f"Timestamp  : {report['timestamp']}")

        if cpu >= CPU_CRITICAL:
            print(
                f"!!! CRITICAL ALERT: {server_id} "
                f"CPU usage is {cpu}% !!!"
            )

        elif cpu >= CPU_WARNING:
            print(
                f"!! WARNING: {server_id} "
                f"CPU usage is {cpu}% !!"
            )

        if memory >= MEMORY_CRITICAL:
            print(
                f"!!! CRITICAL ALERT: {server_id} "
                f"memory usage is {memory}% !!!"
            )

        elif memory >= MEMORY_WARNING:
            print(
                f"!! WARNING: {server_id} "
                f"memory usage is {memory}% !!"
            )

        # Automatically apply or remove SDN restrictions.
        update_sdn_state(server_id, cpu, memory)

    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(f"Invalid health report: {error}")
