# NetPulse — SDN-Based Remote Health Monitoring

## 1. Introduction

NetPulse is a remote system health monitoring and network protection project built using Python, Mininet, Open vSwitch and the OS-Ken SDN controller.

It monitors four simulated hosts, detects abnormal resource usage and dynamically applies network restrictions through OpenFlow rules.

A web dashboard provides live monitoring, network visualization, manual SDN controls and event history.

## 2. Network Architecture

| Node | IP Address | Role |
|---|---|---|
| h1 | 10.0.0.1 | Monitoring server |
| h2 | 10.0.0.2 | Monitored host |
| h3 | 10.0.0.3 | Monitored host |
| h4 | 10.0.0.4 | Monitored host |
| h5 | 10.0.0.5 | Monitored host |
| s1 | — | Open vSwitch |

All five hosts connect to switch s1.

## 3. Health Monitoring

Monitoring agents collect and transmit health reports to h1 using UDP port 5000.

Reports are transmitted every 5 seconds and contain:

- CPU usage
- Memory usage
- Process count
- Network transmission and reception statistics
- Host identity and timestamp

### Monitoring thresholds

| Condition | Threshold |
|---|---|
| Warning | CPU or memory >= 80% |
| Critical | CPU or memory >= 90% |
| Offline | No report for more than 15 seconds |

## 4. SDN-Based Protection

The OS-Ken controller dynamically manages OpenFlow rules.

### OpenFlow priorities

| Priority | Function |
|---|---|
| 300 | Permit UDP health reports from monitored hosts to h1 |
| 200 | Drop other IPv4 traffic from blocked hosts |
| 10 | Normal MAC-learning forwarding |
| 0 | Table-miss handling |

### Automatic protection

When a host reports critical CPU or memory usage, the monitoring server requests the controller to block that host.

Health reports remain permitted so that recovery can be detected.

When the host recovers, the automatic restriction is removed.

### Manual protection

Users can manually block and unblock hosts through the dashboard.

Manual and automatic blocking reasons are tracked separately.

## 5. Web Dashboard

The dashboard is available locally at:

http://127.0.0.1:8080

Features include:

- Live host monitoring
- CPU and memory charts
- Host health indicators
- Network access status
- Manual block/unblock controls
- Individual animated topology connections
- SDN controller status
- Live OpenFlow rules
- Recent monitoring alerts
- Persistent SDN event history

The topology animations represent inferred monitoring activity, not individual captured UDP packets.

## 6. Project Structure

| File | Purpose |
|---|---|
| topology.py | Defines Mininet topology |
| health_agent.py | Collects and sends health reports |
| monitor_server.py | Receives reports and handles alerts |
| netpulse_controller.py | Implements SDN control |
| start_controller.py | Starts OS-Ken controller |
| dashboard/dashboard_bridge.py | Dashboard HTTP backend |
| dashboard/index.html | Dashboard frontend |
| logs/sdn_events.jsonl | SDN event history |
| Makefile | Build and startup shortcuts |

## 7. Running the Project

Start each component in a separate terminal where indicated.

### Step 1: Start Mininet

From the project directory:

    make topology

### Step 2: Start the SDN controller

In another terminal:

    cd ~/health-monitor
    python3 start_controller.py

### Step 3: Connect the switch

Inside the Mininet CLI:

    sh ovs-vsctl set-controller s1 tcp:127.0.0.1:6653
    sh ovs-vsctl set-fail-mode s1 secure

### Step 4: Start the monitoring server

Inside the Mininet CLI:

    h1 python3 -u /home/sanjay/health-monitor/monitor_server.py > /tmp/health-h1.log 2>&1 &

### Step 5: Start the monitoring agents

Inside the Mininet CLI:

    h2 env SERVER_ID=h2 python3 -u /home/sanjay/health-monitor/health_agent.py > /tmp/health-h2.log 2>&1 &
    h3 env SERVER_ID=h3 python3 -u /home/sanjay/health-monitor/health_agent.py > /tmp/health-h3.log 2>&1 &
    h4 env SERVER_ID=h4 python3 -u /home/sanjay/health-monitor/health_agent.py > /tmp/health-h4.log 2>&1 &
    h5 env SERVER_ID=h5 python3 -u /home/sanjay/health-monitor/health_agent.py > /tmp/health-h5.log 2>&1 &

### Step 6: Start the dashboard

In another terminal:

    cd ~/health-monitor
    sudo python3 -u dashboard/dashboard_bridge.py

Open Firefox inside the Ubuntu VM:

    http://127.0.0.1:8080

Note: Replace /home/sanjay/health-monitor with the actual project path if it differs.

## 8. Verification and Testing

### Check Mininet connectivity

    pingall

### Inspect OpenFlow rules

    sh ovs-ofctl -O OpenFlow13 dump-flows s1

### Check Python syntax

    make check

### Test SDN protection

Use the dashboard to manually block and unblock monitored hosts.

Simulate critical health reports to verify automatic blocking and recovery.

Check the SDN event log:

    cat logs/sdn_events.jsonl

## 9. Implementation Notes and Limitations

Mininet hosts share the underlying Linux kernel. Therefore, CPU and memory statistics obtained through /proc represent the Ubuntu VM's resource usage rather than independent physical host measurements.

The dashboard binds to 127.0.0.1 and is intended for local access inside the Ubuntu VM.

## 10. Conclusion

NetPulse demonstrates the integration of socket programming, centralized health monitoring, software-defined networking and web-based visualization.

It demonstrates how network access policies can be dynamically adjusted in response to monitored system conditions.
