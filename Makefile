.PHONY: help check topology controller connect clean

help:
	@echo "NetPulse - SDN Health Monitoring"
	@echo "make check      - Check Python syntax"
	@echo "make topology   - Start Mininet"
	@echo "make controller - Start OS-Ken controller"
	@echo "make connect    - Connect OVS to OS-Ken"
	@echo "make clean      - Clean up Mininet"

check:
	python3 -m py_compile start_controller.py netpulse_controller.py topology.py monitor_server.py health_agent.py tcp_server.py dashboard/dashboard_bridge.py

topology:
	sudo mn --custom topology.py --topo healthmonitor --controller none --switch ovsk,protocols=OpenFlow13

controller:
	python3 start_controller.py

connect:
	sudo ovs-vsctl set-controller s1 tcp:127.0.0.1:6653
	sudo ovs-vsctl set-fail-mode s1 secure

clean:
	sudo mn -c
