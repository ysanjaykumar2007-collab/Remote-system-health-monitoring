import subprocess
import threading
import json
import time
import socket
import struct
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from simulation import start_simulation, restore_host, get_simulation_status, restore_all

# Configuration
INTERFACE = "s1-eth1"
HTTP_PORT = 8080
TIMEOUT = 15

DASHBOARD_DIR = Path(__file__).resolve().parent

HOSTS = ["h2", "h3", "h4", "h5"]

# Latest monitoring information
host_data = {}
recent_alerts = []
lock = threading.Lock()


def get_status(report, last_seen):
    if time.time() - last_seen > TIMEOUT:
        return "offline"

    cpu = float(report.get("cpu", 0))
    memory = float(report.get("memory", 0))

    if cpu >= 90 or memory >= 90:
        return "critical"

    if cpu >= 80 or memory >= 80:
        return "warning"

    return "healthy"


def capture_packets():
    command = [
        "tcpdump",
        "-i", INTERFACE,
        "-U",
        "-w", "-",
        "udp dst port 5000"
    ]

    print("[BRIDGE] Starting packet capture...", flush=True)

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0
    )

    stream = process.stdout

    # Read PCAP global header
    header = stream.read(24)

    if len(header) != 24:
        print("[ERROR] Cannot read packet capture")
        return

    magic = header[:4]

    if magic == b"\xd4\xc3\xb2\xa1":
        endian = "<"
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian = ">"
    elif magic == b"\x4d\x3c\xb2\xa1":
        endian = "<"
    elif magic == b"\xa1\xb2\x3c\x4d":
        endian = ">"
    else:
        print("[ERROR] Unsupported PCAP format")
        return

    while True:
        packet_header = stream.read(16)

        if len(packet_header) != 16:
            break

        _, _, captured_length, _ = struct.unpack(
            endian + "IIII", packet_header
        )

        if captured_length > 65535:
            break

        packet = stream.read(captured_length)

        if len(packet) != captured_length:
            break

        try:
            # Ethernet header
            if len(packet) < 42:
                continue

            if packet[12:14] != b"\x08\x00":
                continue

            # IPv4 header
            ip_start = 14
            ip_header_length = (packet[ip_start] & 15) * 4

            if packet[ip_start + 9] != 17:
                continue

            udp_start = ip_start + ip_header_length

            destination_port = struct.unpack(
                "!H", packet[udp_start + 2:udp_start + 4]
            )[0]

            if destination_port != 5000:
                continue

            payload = packet[udp_start + 8:]

            report = json.loads(payload.decode("utf-8"))

            server_id = report["server_id"]

            if server_id not in HOSTS:
                continue

            current_time = time.time()

            with lock:
                host_data[server_id] = {
                    "report": report,
                    "last_seen": current_time
                }

                status = get_status(report, current_time)

                if status in ("warning", "critical"):
                    recent_alerts.insert(0, {
                        "host": server_id,
                        "status": status,
                        "cpu": report.get("cpu"),
                        "memory": report.get("memory"),
                        "timestamp": current_time
                    })

                    del recent_alerts[20:]

            print(
                f"[LIVE] {server_id} "
                f"CPU={report['cpu']}% "
                f"MEM={report['memory']}%",
                flush=True
            )

        except (ValueError, KeyError, UnicodeDecodeError,
                struct.error, IndexError):
            continue


def build_dashboard_data():
    result = []
    counts = {
        "total": 4,
        "healthy": 0,
        "warning": 0,
        "critical": 0,
        "offline": 0
    }

    with lock:
        for host in HOSTS:
            entry = host_data.get(host)

            if entry is None:
                result.append({
                    "host": host,
                    "ip": f"10.0.0.{int(host[1:])}",
                    "cpu": None,
                    "memory": None,
                    "status": "offline"
                })

                counts["offline"] += 1
                continue

            report = entry["report"]
            status = get_status(
                report, entry["last_seen"]
            )

            counts[status] += 1

            result.append({
                "host": host,
                "ip": f"10.0.0.{int(host[1:])}",
                "cpu": report.get("cpu"),
                "memory": report.get("memory"),
                "processes": report.get("processes"),
                "network_tx": report.get("network_tx"),
                "network_rx": report.get("network_rx"),
                "status": status
            })

        alerts = list(recent_alerts)

    return {
        "mode": "LIVE",
        "counts": counts,
        "hosts": result,
        "alerts": alerts,
        "timestamp": time.time()
    }


SDN_SOCKET = "/tmp/netpulse-control.sock"

HOST_IPS = {
    "h2": "10.0.0.2",
    "h3": "10.0.0.3",
    "h4": "10.0.0.4",
    "h5": "10.0.0.5"
}


def send_controller_command(action, host):
    host_ip = HOST_IPS.get(host)

    if host_ip is None:
        return False, "Invalid host"

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
            return True, f"{action} successful for {host}"

        return False, f"Controller response: {response}"

    except OSError as error:
        return False, f"Controller unavailable: {error}"




def get_sdn_data():
    """Retrieve actual SDN controller connectivity from Open vSwitch."""
    result = {
        "switch": "s1",
        "controller_connected": False,
        "controller_target": None,
        "flows": [],
        "flow_count": 0,
        "error": None
    }

    try:
        process = subprocess.run(
            [
                "ovs-vsctl",
                "--data=bare",
                "--no-heading",
                "--columns=is_connected",
                "list",
                "Controller"
            ],
            capture_output=True,
            text=True,
            timeout=3
        )
        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip())

        result["controller_connected"] = (
            process.stdout.strip().lower() == "true"
        )

    except (subprocess.TimeoutExpired, OSError, RuntimeError) as error:
        result["error"] = str(error)


    try:
        process = subprocess.run(
            [
                "ovs-ofctl",
                "-O", "OpenFlow13",
                "dump-flows", "s1"
            ],
            capture_output=True,
            text=True,
            timeout=3
        )

        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip())

        result["flows"] = [
            line.strip()
            for line in process.stdout.splitlines()
            if "priority=" in line
        ]

        result["flow_count"] = len(result["flows"])

    except (subprocess.TimeoutExpired, OSError, RuntimeError) as error:
        result["error"] = str(error)

    return result

class DashboardHandler(BaseHTTPRequestHandler):
    def do_simulation_POST(self):
        if self.path in ("/api/simulate", "/api/restore"):
            try:
                length = int(self.headers.get("Content-Length", "0"))

                if length <= 0 or length > 4096:
                    raise ValueError("Invalid request size")

                request = json.loads(
                    self.rfile.read(length).decode()
                )

                host = request.get("host")

                if self.path == "/api/simulate":
                    message = start_simulation(
                        host,
                        request.get("cpu"),
                        request.get("memory")
                    )
                else:
                    message = restore_host(host)

                status = 200
                response = {
                    "success": True,
                    "message": message
                }

            except (ValueError, TypeError, RuntimeError, OSError) as error:
                status = 400
                response = {
                    "success": False,
                    "message": str(error)
                }

            data = json.dumps(response).encode()

            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return

    def do_manual_POST(self):
        if self.path not in ("/api/block", "/api/unblock"):
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))

            if length <= 0 or length > 4096:
                raise ValueError("Invalid request size")

            body = self.rfile.read(length)
            request = json.loads(body.decode())

            host = request.get("host")

            action = (
                "manual_block"
                if self.path == "/api/block"
                else "manual_unblock"
            )

            success, message = send_controller_command(
                action, host
            )

            status = 200 if success else 400

        except (ValueError, TypeError, AttributeError):
            success = False
            message = "Invalid JSON request"
            status = 400

        response = json.dumps({
            "success": success,
            "message": message
        }).encode()

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(response)



    def do_POST(self):
        if self.path in ("/api/simulate", "/api/restore"):
            return self.do_simulation_POST()
        return self.do_manual_POST()

    def do_simulation_GET(self):
        if self.path == "/api/simulation":
            data = json.dumps({
                "simulations": get_simulation_status()
            }).encode()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return

    def do_GET(self):
        if self.path == "/api/simulation":
            return self.do_simulation_GET()
        return self.do_existing_GET()

    def do_existing_GET(self):
        if self.path == "/api/events":
            log_path = (
                Path(__file__).resolve().parent.parent
                / "logs" / "sdn_events.jsonl"
            )

            events = []

            try:
                with log_path.open("r", encoding="utf-8") as log:
                    for line in log:
                        if not line.strip():
                            continue

                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

            except FileNotFoundError:
                pass
            except OSError as error:
                self.send_error(500, str(error))
                return

            data = json.dumps({
                "events": events[-50:][::-1],
                "count": len(events)
            }).encode()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return

        if self.path == "/api/sdn":
            data = json.dumps(get_sdn_data()).encode()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return

        if self.path == "/api/status":
            data = json.dumps(
                build_dashboard_data()
            ).encode()

            self.send_response(200)
            self.send_header(
                "Content-Type", "application/json"
            )
            self.send_header(
                "Cache-Control", "no-store"
            )
            self.end_headers()
            self.wfile.write(data)

        elif self.path in ("/", "/index.html"):
            html = (
                DASHBOARD_DIR / "index.html"
            ).read_bytes()

            self.send_response(200)
            self.send_header(
                "Content-Type", "text/html"
            )
            self.end_headers()
            self.wfile.write(html)

        else:
            self.send_error(404)


if __name__ == "__main__":

    threading.Thread(
        target=capture_packets,
        daemon=True
    ).start()

    server = HTTPServer(
        ("127.0.0.1", HTTP_PORT),
        DashboardHandler
    )

    print(
        f"[BRIDGE] Dashboard available on "
        f"http://127.0.0.1:{HTTP_PORT}",
        flush=True
    )

    server.serve_forever()
