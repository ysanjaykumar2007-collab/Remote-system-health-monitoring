import json
import math
import os
import signal
import subprocess
import threading
import time

HOSTS = {"h2", "h3", "h4", "h5"}
MONITOR_IP = "10.0.0.1"
MONITOR_PORT = 5000
INTERVAL = 5

simulations = {}
lock = threading.RLock()


def find_agent(host):
    """Find the running health agent belonging to a Mininet host."""

    if host not in HOSTS:
        raise ValueError("Invalid host")

    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue

        pid = int(entry)

        try:
            with open(f"/proc/{pid}/cmdline", "rb") as file:
                args = file.read().replace(b"\x00", b" ").decode()

            if "health_agent.py" not in args:
                continue

            with open(f"/proc/{pid}/environ", "rb") as file:
                environment = file.read().split(b"\x00")

            if f"SERVER_ID={host}".encode() in environment:
                return pid

        except (OSError, UnicodeDecodeError):
            continue

    raise RuntimeError(f"No running health agent found for {host}")


def validate_percentage(value, name):
    """Accept only finite numeric percentages between 0 and 100."""

    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number")

    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number")

    if not math.isfinite(number) or not 0 <= number <= 100:
        raise ValueError(f"{name} must be between 0 and 100")

    return number


def send_report(host, pid, cpu, memory):
    """Send a simulated UDP report from the host's network namespace."""

    report = {
        "server_id": host,
        "cpu": cpu,
        "memory": memory,
        "processes": 0,
        "network_tx": 0,
        "network_rx": 0,
        "timestamp": time.time()
    }

    sender = (
        "import json,socket,sys;"
        "s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);"
        "s.sendto(json.dumps(json.loads(sys.argv[1])).encode(),"
        "('10.0.0.1',5000));"
        "s.close()"
    )

    subprocess.run(
        [
            "mnexec", "-a", str(pid),
            "python3", "-c", sender,
            json.dumps(report)
        ],
        check=True,
        timeout=4,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )


def simulation_worker(host, state):
    """Keep sending simulated readings until restoration."""

    try:
        while not state["stop"].is_set():
            try:
                with lock:
                    cpu = state["cpu"]
                    memory = state["memory"]

                send_report(host, state["pid"], cpu, memory)

            except (OSError, subprocess.SubprocessError) as error:
                state["error"] = str(error)
                break

            if state["stop"].wait(INTERVAL):
                break

    finally:
        with lock:
            if simulations.get(host) is state:
                simulations.pop(host, None)

        # Resume the agent even if simulation encounters an error.
        try:
            os.kill(state["pid"], signal.SIGCONT)
        except ProcessLookupError:
            pass


def start_simulation(host, cpu, memory):
    """Pause a host's real agent and begin custom reporting."""

    if host not in HOSTS:
        raise ValueError("Invalid host")

    cpu = validate_percentage(cpu, "CPU")
    memory = validate_percentage(memory, "Memory")

    with lock:
        existing = simulations.get(host)

        if existing:
            existing["cpu"] = cpu
            existing["memory"] = memory
            return f"Simulation updated for {host}"

        pid = find_agent(host)

        state = {
            "pid": pid,
            "cpu": cpu,
            "memory": memory,
            "stop": threading.Event(),
            "error": None
        }

        os.kill(pid, signal.SIGSTOP)

        simulations[host] = state

        try:
            worker = threading.Thread(
                target=simulation_worker,
                args=(host, state),
                daemon=True
            )
            state["worker"] = worker
            worker.start()

        except Exception:
            simulations.pop(host, None)
            os.kill(pid, signal.SIGCONT)
            raise

    return f"Simulation started for {host}: CPU={cpu}%, Memory={memory}%"


def restore_host(host):
    """Stop simulation and resume the real health agent."""

    if host not in HOSTS:
        raise ValueError("Invalid host")

    with lock:
        state = simulations.get(host)

        if state is None:
            return f"{host} is already in normal monitoring mode"

        state["stop"].set()
        worker = state["worker"]

    worker.join(timeout=6)

    if worker.is_alive():
        raise RuntimeError(f"Simulation for {host} has not stopped yet")

    # The worker's finally block resumes the original agent.
    return f"Normal monitoring restored for {host}"


def get_simulation_status():
    """Return currently simulated hosts for the dashboard."""

    with lock:
        return {
            host: {
                "cpu": state["cpu"],
                "memory": state["memory"],
                "active": True
            }
            for host, state in simulations.items()
        }


def restore_all():
    """Attempt to restore every simulated agent."""

    with lock:
        hosts = list(simulations)

    for host in hosts:
        try:
            restore_host(host)
        except Exception as error:
            print(f"[SIMULATION] Failed to restore {host}: {error}")
