import json
import os
import socket
import threading
from datetime import datetime

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import (
    CONFIG_DISPATCHER,
    MAIN_DISPATCHER,
    set_ev_cls,
)
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, ether_types


SOCKET_PATH = "/tmp/netpulse-control.sock"
MONITOR_IP = "10.0.0.1"
MONITOR_PORT = 5000


class NetPulseController(app_manager.OSKenApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mac_to_port = {}
        self.datapaths = {}
        self.blocked_hosts = set()
        self.manual_blocks = set()
        self.automatic_blocks = set()
        self.state_lock = threading.Lock()

        print("[NETPULSE] SDN controller initialized")

        threading.Thread(
            target=self.command_server,
            daemon=True
        ).start()

    def record_event(self, host_ip, action, source, access_changed):
        """Record a controller action in JSON Lines format."""
        event = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "host": "h" + host_ip.rsplit(".", 1)[-1],
            "ip": host_ip,
            "action": action,
            "source": source,
            "access_changed": access_changed
        }

        log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "logs",
            "sdn_events.jsonl"
        )

        try:
            with open(log_path, "a", encoding="utf-8") as log:
                log.write(json.dumps(event) + "\n")
        except OSError as error:
            print(f"[NETPULSE] Event logging failed: {error}")

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions
        )

        datapath.send_msg(mod)

    def remove_flow(self, datapath, priority, match):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE_STRICT,
            priority=priority,
            match=match,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY
        )

        datapath.send_msg(mod)

    def monitoring_match(self, parser, host_ip):
        return parser.OFPMatch(
            eth_type=0x0800,
            ipv4_src=host_ip,
            ipv4_dst=MONITOR_IP,
            ip_proto=17,
            udp_dst=MONITOR_PORT
        )

    def blocking_match(self, parser, host_ip):
        return parser.OFPMatch(
            eth_type=0x0800,
            ipv4_src=host_ip
        )

    def install_block(self, datapath, host_ip):
        parser = datapath.ofproto_parser

        # Allow health reports to reach h1 on switch port 1.
        self.add_flow(
            datapath,
            300,
            self.monitoring_match(parser, host_ip),
            [parser.OFPActionOutput(1)]
        )

        # Drop other IPv4 traffic from this host.
        self.add_flow(
            datapath,
            200,
            self.blocking_match(parser, host_ip),
            []
        )

    def remove_block(self, datapath, host_ip):
        parser = datapath.ofproto_parser

        self.remove_flow(
            datapath,
            300,
            self.monitoring_match(parser, host_ip)
        )

        self.remove_flow(
            datapath,
            200,
            self.blocking_match(parser, host_ip)
        )

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        with self.state_lock:
            self.datapaths[datapath.id] = datapath
            blocked = list(self.blocked_hosts)

        self.add_flow(
            datapath,
            0,
            parser.OFPMatch(),
            [
                parser.OFPActionOutput(
                    ofproto.OFPP_CONTROLLER,
                    ofproto.OFPCML_NO_BUFFER
                )
            ]
        )

        # Synchronize NetPulse restrictions after reconnection.
        # Remove stale restrictions, then reinstall active ones.
        for host_ip in (
            "10.0.0.2",
            "10.0.0.3",
            "10.0.0.4",
            "10.0.0.5"
        ):
            self.remove_block(datapath, host_ip)

        for host_ip in blocked:
            self.install_block(datapath, host_ip)

        print("[NETPULSE] Switch connected:", datapath.id)

    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER
    )
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None:
            return

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src = eth.src
        dst = eth.dst
        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        out_port = self.mac_to_port[dpid].get(
            dst,
            ofproto.OFPP_FLOOD
        )

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst
            )

            self.add_flow(
                datapath,
                10,
                match,
                actions
            )

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )

        datapath.send_msg(out)

    def block_host(self, host_ip, source="automatic"):
        if source not in ("manual", "automatic"):
            return False

        with self.state_lock:
            reasons = (
                self.manual_blocks
                if source == "manual"
                else self.automatic_blocks
            )

            if host_ip in reasons:
                return True

            reasons.add(host_ip)
            access_changed = host_ip not in self.blocked_hosts

            if access_changed:
                self.blocked_hosts.add(host_ip)

            datapaths = list(self.datapaths.values()) if access_changed else []

        for datapath in datapaths:
            self.install_block(datapath, host_ip)

        self.record_event(host_ip, "blocked", source, access_changed)

        if access_changed:
            print(f"[NETPULSE] BLOCKED: {host_ip} ({source})")

        return True

    def unblock_host(self, host_ip, source="automatic"):
        if source not in ("manual", "automatic"):
            return False

        with self.state_lock:
            reasons = (
                self.manual_blocks
                if source == "manual"
                else self.automatic_blocks
            )

            if host_ip not in reasons:
                return True

            reasons.remove(host_ip)

            access_changed = (
                host_ip in self.blocked_hosts
                and host_ip not in self.manual_blocks
                and host_ip not in self.automatic_blocks
            )

            if access_changed:
                self.blocked_hosts.remove(host_ip)

            datapaths = list(self.datapaths.values()) if access_changed else []

        for datapath in datapaths:
            self.remove_block(datapath, host_ip)

        self.record_event(host_ip, "unblocked", source, access_changed)

        if access_changed:
            print(f"[NETPULSE] UNBLOCKED: {host_ip} ({source})")

        return True

    def command_server(self):
        # Remove a stale socket left by a previous run.
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)

        server = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM
        )

        try:
            server.bind(SOCKET_PATH)

            # The monitoring server runs in Mininet's h1
            # namespace but shares the filesystem.
            os.chmod(SOCKET_PATH, 0o660)

            server.listen(5)

            print(
                "[NETPULSE] Command socket ready:",
                SOCKET_PATH
            )

            while True:
                conn, _ = server.accept()

                try:
                    data = conn.recv(4096)
                    command = json.loads(data.decode())

                    action = command.get("action")
                    host_ip = command.get("host_ip")

                    # Only allow known monitoring agents.
                    allowed_hosts = {
                        "10.0.0.2",
                        "10.0.0.3",
                        "10.0.0.4",
                        "10.0.0.5"
                    }

                    if host_ip not in allowed_hosts:
                        conn.sendall(b"INVALID_HOST")

                    elif action == "block":
                        self.block_host(host_ip)
                        conn.sendall(b"OK")

                    elif action == "unblock":
                        self.unblock_host(host_ip)
                        conn.sendall(b"OK")

                    elif action == "manual_block":
                        self.block_host(host_ip, source="manual")
                        conn.sendall(b"OK")

                    elif action == "manual_unblock":
                        self.unblock_host(host_ip, source="manual")
                        conn.sendall(b"OK")

                    else:
                        conn.sendall(b"INVALID_ACTION")

                except Exception as error:
                    print("[NETPULSE] Command error:", error)
                    try:
                        conn.sendall(b"ERROR")
                    except OSError:
                        pass

                finally:
                    conn.close()

        finally:
            server.close()

            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)
