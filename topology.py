from mininet.topo import Topo


class HealthMonitorTopo(Topo):

    def build(self):

        # Central monitoring server
        monitor = self.addHost(
            'h1',
            ip='10.0.0.1/24'
        )

        # Four monitored servers
        server1 = self.addHost(
            'h2',
            ip='10.0.0.2/24'
        )

        server2 = self.addHost(
            'h3',
            ip='10.0.0.3/24'
        )

        server3 = self.addHost(
            'h4',
            ip='10.0.0.4/24'
        )

        server4 = self.addHost(
            'h5',
            ip='10.0.0.5/24'
        )

        # SDN/OpenFlow switch
        switch = self.addSwitch('s1')

        # Connect all hosts to the switch
        self.addLink(monitor, switch)
        self.addLink(server1, switch)
        self.addLink(server2, switch)
        self.addLink(server3, switch)
        self.addLink(server4, switch)


topos = {
    'healthmonitor': HealthMonitorTopo
}
