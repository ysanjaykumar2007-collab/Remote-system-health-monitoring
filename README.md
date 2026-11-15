# NetPulse — SDN-Based Remote Health Monitoring
## Team Members

| Name | SRN |
|------|-----|
| Y Sanjay Kumar | PES1UG25AM535 |
| Tejas Gowda M N | PES1UG25AM531 |
| Ranjani | PES1UG25AM543 |

A Python-based remote health monitoring and network protection system built using **Mininet, Open vSwitch, OS-Ken and OpenFlow 1.3**.

NetPulse monitors simulated hosts, detects abnormal resource usage, and dynamically applies network access restrictions through an SDN controller. A web dashboard provides real-time monitoring, network visualization and manual network controls.

---

## 1. Project Overview

NetPulse demonstrates the integration of:

- Socket programming using UDP and TCP.
- Centralized system health monitoring.
- Software-Defined Networking (SDN).
- Dynamic OpenFlow rule management.
- Automated host blocking and recovery.
- Real-time web-based monitoring.

## 2. Network Architecture

The project uses a Mininet topology containing five hosts connected through an Open vSwitch.

| Node | IP Address | Role |
|---|---|---|
| h1 | 10.0.0.1 | Central monitoring server |
| h2 | 10.0.0.2 | Monitored host |
| h3 | 10.0.0.3 | Monitored host |
| h4 | 10.0.0.4 | Monitored host |
| h5 | 10.0.0.5 | Monitored host |
| s1 | — | Open vSwitch |

The OS-Ken controller manages the switch through OpenFlow 1.3.

### Architecture workflow

1. Monitoring agents collect host resource statistics.
2. Agents transmit reports to h1 using UDP.
3. The monitoring server evaluates incoming reports.
4. Critical conditions trigger SDN control requests.
5. The controller installs or removes OpenFlow rules.
6. The dashboard displays monitoring information and network access status.

## 3. Health Monitoring

Each monitored host runs a Python health agent.

Reports are transmitted every five seconds through UDP port **5000**.

Collected information includes:

- CPU utilization.
- Memory utilization.
- Process count.
- Network transmission statistics.
- Network reception statistics.
- Host identity and timestamp.

### Monitoring thresholds

| Condition | Threshold |
|---|---|
| Warning | CPU or memory ≥ 80% |
| Critical | CPU or memory ≥ 90% |
| Offline | No report for more than 15 seconds |

## 4. SDN-Based Network Protection

The OS-Ken controller dynamically manages OpenFlow rules on switch s1.

### OpenFlow priorities

| Priority | Function |
|---|---|
| 300 | Permit UDP health reports from monitored hosts |
| 200 | Block other IPv4 traffic from restricted hosts |
| 10 | Normal MAC-learning forwarding |
| 0 | Table-miss handling |

### Automatic protection

When a monitored host reaches a critical CPU or memory threshold:

1. The monitoring server detects the critical condition.
2. It sends a blocking request to the SDN controller.
3. The controller installs a higher-priority blocking rule.
4. Health reports remain permitted.
5. Once the host recovers, the automatic restriction is removed.

### Manual protection

The dashboard also provides manual block and unblock controls.

Manual and automatic blocking reasons are tracked separately, preventing one type of restriction from incorrectly removing another.

## 5. Communication Services

| Protocol | Port | Purpose |
|---|---:|---|
| UDP | 5000 | Periodic health reports |
| TCP | 6000 | Standalone TCP health service |
| HTTP | 8080 | Web dashboard |

UDP is used for periodic health reporting, while the TCP service provides a separate basic health-response mechanism.

## 6. Web Dashboard

The dashboard provides a centralized interface for monitoring the simulated network.

Features include:

- Live host monitoring.
- CPU and memory usage charts.
- Warning, critical and offline indicators.
- Network access status.
- Individual animated network connections.
- Manual host blocking and unblocking.
- SDN controller status.
- Live OpenFlow rule inspection.
- Recent monitoring alerts.
- SDN event history.

The topology animations represent inferred monitoring activity based on live reporting and network access state. They should not be interpreted as individual packet-by-packet animations.

Dashboard address:

`http://127.0.0.1:8080`

## 7. Project Structure

```text
Remote-system-health-monitoring/
│
├── dashboard/
│   ├── dashboard_bridge.py
│   └── index.html
│
├── logs/
│   └── .gitkeep
│
├── controller/
│   (development copies excluded from submission)
│
├── health_agent.py
├── monitor_server.py
├── netpulse_controller.py
├── start_controller.py
├── tcp_server.py
├── topology.py
├── Makefile
├── requirements.txt
├── .gitignore
└── README.md
```

The authoritative implementations are the root-level Python files and the dashboard files.

Runtime SDN event records are generated in `logs/sdn_events.jsonl` and are intentionally excluded from Git.

## 8. Installation and Prerequisites

Required software:

- Ubuntu Linux.
- Python 3.
- Mininet.
- Open vSwitch.
- OS-Ken.
- tcpdump.

Install the system dependencies:

```bash
sudo apt update
sudo apt install mininet openvswitch-switch tcpdump python3-venv -y
```

Clone the repository:

```bash
git clone https://github.com/ysanjaykumar2007-collab/Remote-system-health-monitoring.git ~/health-monitor
cd ~/health-monitor
```

Create a Python virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 9. Running the Project

### Recommended Method: Automated Startup

NetPulse provides an automated startup script that launches the
SDN controller, Mininet network, monitoring services, and web dashboard.

From the project directory, run:

```bash
cd ~/health-monitor
./start_netpulse.sh
```

Open the dashboard in Firefox:

http://127.0.0.1:8080

To stop NetPulse, type `exit` in the Mininet CLI.

### Alternative Method: Manual Startup

The following steps describe manual startup for troubleshooting.


### Step 1: Start Mininet

```bash
cd ~/health-monitor
make topology
```

### Step 2: Start the SDN controller

In another terminal, activate the virtual environment:

```bash
cd ~/health-monitor
source .venv/bin/activate
python3 start_controller.py
```

### Step 3: Connect the switch

Inside the Mininet CLI:

```bash
sh ovs-vsctl set-controller s1 tcp:127.0.0.1:6653
sh ovs-vsctl set-fail-mode s1 secure
```

### Step 4: Start the monitoring server

Inside the Mininet CLI:

```bash
h1 python3 -u /home/USER/health-monitor/monitor_server.py
```

Replace `USER` with the Ubuntu username.

### Step 5: Start monitoring agents

In the Mininet CLI:

```bash
h2 env SERVER_ID=h2 python3 -u /home/USER/health-monitor/health_agent.py &
h3 env SERVER_ID=h3 python3 -u /home/USER/health-monitor/health_agent.py &
h4 env SERVER_ID=h4 python3 -u /home/USER/health-monitor/health_agent.py &
h5 env SERVER_ID=h5 python3 -u /home/USER/health-monitor/health_agent.py &
```

### Step 6: Start the dashboard

In another Ubuntu terminal:

```bash
cd ~/health-monitor
sudo .venv/bin/python dashboard/dashboard_bridge.py
```

Open Firefox inside the Ubuntu VM:

`http://127.0.0.1:8080`

### Optional: Start the TCP health service

Run this separately on the intended Mininet host:

```bash
h2 python3 -u /home/USER/health-monitor/tcp_server.py
```

The TCP service listens on port 6000.

## 10. Verification and Testing

### Check network connectivity

Inside Mininet:

```bash
pingall
```

### Inspect OpenFlow rules

```bash
sh ovs-ofctl -O OpenFlow13 dump-flows s1
```

### Check Python syntax

```bash
make check
```

### Verify monitoring

Inspect the monitoring server output and confirm that reports arrive from h2, h3, h4 and h5.

### Verify SDN protection

Use the dashboard to manually block and unblock hosts.

Simulate critical resource reports to test automatic blocking and recovery.

Inspect the event history:

```bash
cat logs/sdn_events.jsonl
```

## 11. Implementation Notes and Limitations

- Mininet hosts share the underlying Linux kernel. Therefore, CPU and memory statistics obtained through `/proc` represent the Ubuntu VM's resource usage rather than independent physical host measurements.
- The dashboard binds to `127.0.0.1` and is intended for local access inside the Ubuntu VM.
- The topology animation is a visualization of monitoring and access state, not a packet-by-packet replay.
- The project is designed as an educational SDN demonstration environment.

## 12. Conclusion

NetPulse demonstrates how socket programming, centralized health monitoring and Software-Defined Networking can be integrated into a single system.

By combining UDP-based monitoring, TCP communication, dynamic OpenFlow rule management and a real-time dashboard, the project demonstrates how network access policies can be adjusted in response to monitored system conditions.

---

**Technologies:** Python · Mininet · Open vSwitch · OS-Ken · OpenFlow 1.3 · HTML · CSS · JavaScript
---

## Project Screenshots

The following screenshots demonstrate the implementation and testing of NetPulse.

| Screenshot | Description |
|---|---|
| [Main Dashboard](screenshots/01_dashboard.png) | Live health monitoring overview |
| [Network Topology](screenshots/02_topology.png) | Mininet topology and SDN controller |
| [Host Monitoring](screenshots/03_host_monitoring.png) | CPU, memory and host status |
| [Automatic Blocking](screenshots/04_automatic_block.png) | SDN protection triggered by critical resource usage |
| [Automatic Recovery](screenshots/05_recovery.png) | Network access restored after recovery |
| [Event Logs](screenshots/06_event_logs.png) | History of SDN blocking and unblocking events |
---

## Individual Contributions

### 1. Tejas Gowda M N (PES1UG25AM531)
**Network Topology and Setup**
- Developed and configured the Mininet network topology.
- Configured virtual hosts and Open vSwitch.
- Established network connectivity between monitoring nodes.

### 2. Ranjani (PES1UG25AM543)
**Health Monitoring and SDN Controller**
- Developed the health monitoring server and agents.
- Implemented CPU and memory monitoring.
- Implemented SDN-based automatic blocking and recovery using OpenFlow rules.

### 3. Y Sanjay Kumar (PES1UG25AM535)
**Web Dashboard, Testing and Documentation**
- Developed the web dashboard for real-time monitoring.
- Implemented host visualization, network topology display, and event logs.
- Tested manual blocking, automatic blocking, and recovery.
- Captured screenshots and prepared project documentation.
- Managed the GitHub repository and README.
