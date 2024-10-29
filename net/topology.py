import json
import xml.etree.ElementTree as ET
import re
import logging
import ipaddress

logger = logging.getLogger(__name__)


class TopologyError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors


class UserHost:
    name = ""
    os = ""
    ip = ""
    gateway = ""
    switcher = ""

    def __init__(self, name, os, ip, gateway, switcher):
        self.name = name
        self.os = os
        self.ip = ip
        self.gateway = gateway
        self.switcher = switcher

        if not is_valid_C_ip(ip):
            raise TopologyError(f"Invalid IP for host {name}: {ip}")
        # if not is_valid_gateway(gateway):
        #     raise TopologyError(f"Invalid gateway for host {name}: {gateway}")


class UserSwitcher:
    name = ""
    ports = 8
    mgmt_ip = ""
    vlan = ""
    cascading = []

    def __init__(self, name, ports, mgmt_ip, vlan):
        self.name = name
        self.ports = ports
        self.mgmt_ip = mgmt_ip
        self.vlan = vlan
        self.cascading = []

        # try:
        #     self.ports = int(ports)
        #     self.vlan = int(vlan)
        # except ValueError as e:
        #     raise TopologyError(f"Invalid ports or vlan for switch {name}: {e}")


class UserRouter:
    name = ""
    ports = []
    category = ""
    rules = []

    def __init__(self, name, category="router", rules=None):
        if rules is None:
            self.rules = []
        self.name = name
        self.ports = []
        self.category = category
        self.rules = rules

    def add_port(self, port_name, routing, ip, bandwidth, delay, loss, switcher):
        port = {
            'name': port_name,
            'routing': routing,
            'ip': ip,
            'bandwidth': bandwidth,
            'delay': delay,
            'loss': loss,
            'switcher': switcher
        }
        self.ports.append(port)
        if not is_valid_C_ip(ip):
            raise TopologyError(f"Invalid IP for router {self.name} port {port_name}: {ip}")


class UserFirewall(UserRouter):
    def __init__(self, name, rules=None):
        super().__init__(name, category="firewall", rules=rules)


def check_required_fields(elem, fields):
    for field in fields:
        if not elem.get(field):
            raise TopologyError(f"{elem.tag} missing required field: {field}")


def is_valid_C_ip(ip):
    return re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$", ip) is not None


def is_valid_gateway(ip):
    return re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip) is not None


class UserTopology:
    hosts = []
    switches = []
    routers = []
    IPRange = []
    HostNameList = []
    SwitchNameList = []
    RouterNameList = []

    def __init__(self):
        self.hosts = []
        self.switches = []
        self.routers = []

    def add_IPRange(self, IPAddr):
        unique = True
        for ip in self.IPRange:
            if ipaddress.ip_address(ip) == ipaddress.ip_address(IPAddr):
                unique = False
        if unique:
            self.IPRange.append(IPAddr)

    def add_host(self, host):
        self.hosts.append(host)

    def add_switch(self, switch):
        self.switches.append(switch)

    def add_router(self, router):
        self.routers.append(router)

    def to_json(self):
        hosts_data = []
        for host in self.hosts:
            host_data = {
                "name": host.name,
                "os": host.os,
                "ip": host.ip,
                "gateway": host.gateway,
                "switcher": host.switcher
            }
            hosts_data.append(host_data)

        switches_data = []
        for switch in self.switches:
            switch_data = {
                "name": switch.name,
                "ports": switch.ports,
                "mgmt_ip": switch.mgmt_ip,
                "vlan": switch.vlan,
                "cascading": switch.cascading
            }
            switches_data.append(switch_data)

        routers_data = []
        for router in self.routers:
            ports_data = []
            for port in router.ports:
                port_data = {
                    "port_name": port['name'],
                    "ip": port['ip'],
                    "bandwidth": port['bandwidth'],
                    "delay": port['delay'],
                    "loss": port['loss'],
                    "switcher": port['switcher']
                }
                if not isinstance(router, UserFirewall):
                    port_data["routing"] = port['routing']
                ports_data.append(port_data)

            rules_data = []
            if isinstance(router, UserFirewall):
                for rule in router.rules:
                    rule_data = {
                        "sip": rule['sa'],
                        "dip": rule['da'],
                        "sport": rule['sp'],
                        "dport": rule['dp'],
                        "protocol": rule['protocol'],
                        "policy": rule['policy']
                    }
                    rules_data.append(rule_data)

            router_data = {
                "name": router.name,
                "category": router.category,
                "ports": ports_data,
                "rules": rules_data
            }
            routers_data.append(router_data)

        topology_data = {
            "hosts": hosts_data,
            "switches": switches_data,
            "gateway": routers_data
        }

        return topology_data

    @classmethod
    def from_json(cls, data):
        topology = cls()

        # Parse hosts
        for host_data in data['hosts']:
            name = host_data['name']
            os = host_data['os']
            ip = host_data['ip']
            gateway = host_data['gateway']
            switcher = host_data['switcher']

            host = UserHost(name, os, ip, gateway, switcher)
            topology.add_host(host)
            topology.HostNameList.append(name)
            # topology.add_IPRange(ip)

        # Parse switches
        for switch_data in data['switches']:
            name = switch_data['name']
            ports = switch_data['ports']
            mgmt_ip = switch_data['mgmt_ip']
            vlan = switch_data['vlan']

            switch = UserSwitcher(name, ports, mgmt_ip, vlan)
            switch.cascading = switch_data['cascading']
            topology.add_switch(switch)
            topology.SwitchNameList.append(name)

        # Parse routers
        for router_data in data['gateway']:
            name = router_data['name']
            category = router_data['category']
            if category == 'firewall':
                rules = []
                for rule in router_data['rules']:
                    rules.append({'sa': rule['sip'], 'da': rule['dip'], 'sp': rule['sport'], 'dp': rule['dport'],
                                  'protocol': rule['protocol'], 'policy': rule['policy']})
                router = UserFirewall(name, rules)
            else:
                router = UserRouter(name)

            if isinstance(router, UserFirewall):
                for port_data in router_data['ports']:
                    port_name = port_data['port_name']
                    ip = port_data['ip']
                    bandwidth = port_data['bandwidth']
                    delay = port_data['delay']
                    loss = port_data['loss']
                    switcher = port_data['switcher']
                    # topology.add_IPRange(ip)
                    router.add_port(port_name, '', ip, bandwidth, delay, loss, switcher)
            else:
                for port_data in router_data['ports']:
                    port_name = port_data['port_name']
                    routing = port_data['routing']
                    ip = port_data['ip']
                    bandwidth = port_data['bandwidth']
                    delay = port_data['delay']
                    loss = port_data['loss']
                    switcher = port_data['switcher']
                    # topology.add_IPRange(ip)
                    router.add_port(port_name, routing, ip, bandwidth, delay, loss, switcher)
            topology.add_router(router)
            topology.RouterNameList.append(name)
        return topology

    @classmethod
    def from_xml_file(cls, file):
        root = ET.fromstring(file)

        topology = UserTopology()

        for host_elem in root.findall('host'):
            for host in host_elem:
                name, attrs = host.tag, host.text.split(', ')
                os, ip, gateway, switcher = attrs
                try:
                    host_obj = UserHost(name, os, ip, gateway, switcher)
                    topology.add_host(host_obj)
                except ValueError as e:
                    logger.error(f"Failed to add host: {e}")

        # Parse switches
        for switch_elem in root.findall('switcher'):
            for switch in switch_elem:
                name, attrs = switch.tag, switch.text.split(', ')
                ports, mgmt_ip, vlan, cascading = attrs
                try:
                    switch_obj = UserSwitcher(name, ports, mgmt_ip, vlan)
                    if cascading:
                        switch_obj.cascading = cascading.split(', ')
                    topology.add_switch(switch_obj)
                except ValueError as e:
                    logger.error(f"Failed to add switch: {e}")

        # Parse routers
        for router_elem in root.findall('router'):
            for fw in router_elem:
                name = fw.tag
                router_obj = UserRouter(name)

                for port in fw.findall('ports/port'):
                    port_attrs = port.text.split(',')
                    if len(port_attrs) == 7:
                        port_name, routing, ip, bw, delay, loss, switcher = port_attrs
                    else:
                        port_name, ip, bw, delay, loss, switcher = port_attrs
                        routing = ''
                    router_obj.add_port(port_name, routing, ip, bw, delay, loss, switcher)

                topology.add_router(router_obj)
        for firewall_elem in root.findall('firewall'):
            for fw in firewall_elem:
                name = fw.tag
                rules = []
                for rule in fw.findall('rules/rule'):
                    sa, da, sp, dp, protocol, policy = rule.text.split(',')
                    rules.append({'sa': sa, 'da': da, 'sp': sp, 'dp': dp, 'protocol': protocol, 'policy': policy})
                router_obj = UserFirewall(name, rules)

                for port in fw.findall('ports/port'):
                    port_attrs = port.text.split(',')
                    if len(port_attrs) == 7:
                        port_name, routing, ip, bw, delay, loss, switcher = port_attrs
                    else:
                        port_name, ip, bw, delay, loss, switcher = port_attrs
                        routing = ''
                    router_obj.add_port(port_name, routing, ip, bw, delay, loss, switcher)

                topology.add_router(router_obj)

        return topology


class GraphNode:
    def __init__(self, node_id, label, category, routings=None, rules=None):
        self.node_id = node_id
        self.label = label
        self.category = category
        self.routings = routings
        self.rules = rules


class GraphEdge:
    def __init__(self, from_node_id, to_node_id, from_veth_id, to_veth_id):
        self.from_node_id = from_node_id
        self.to_node_id = to_node_id
        self.from_veth_id = from_veth_id
        self.to_veth_id = to_veth_id
        self.hash = self.hash()

    def hash(self):
        fnodeid = hash(self.from_node_id)
        tnodeid = hash(self.to_node_id)
        return hash((min(fnodeid, tnodeid), max(fnodeid, tnodeid)))


class GraphVeth:
    def __init__(self, eth_id, parent, inet=None, gateway=None, link=None, vlanid=None):
        self.eth_id = eth_id
        self.parent = parent
        self.inet = inet
        self.gateway = gateway
        self.link = link
        self.vlanid = vlanid


class GraphTopology:
    def __init__(self):
        self.nodes = set()
        self.edges = set()
        self.veths = set()

    def add_node(self, node):
        if not isinstance(node, GraphNode):
            raise TopologyError(f"Expect GraphNode but got {type(node)}")
        self.nodes.add(node)

    def add_edge(self, edge):
        if not isinstance(edge, GraphEdge):
            raise TopologyError(f"Expect GraphEdge but got {type(edge)}")
        self.edges.add(edge)

    def add_veth(self, veth):
        if not isinstance(veth, GraphVeth):
            raise TopologyError(f"Expect GraphVeth but got {type(veth)}")

        if veth.parent not in [n.node_id for n in self.nodes]:
            raise TopologyError(f"Veth {veth.eth_id} has unknown parent {veth.parent}")

        self.veths.add(veth)


def convert_topology(xml_topo):
    json_topo = GraphTopology()

    with open("/tmp/exampleTopo.json", 'w') as f:
        json.dump(xml_topo.to_json(), f, indent=4)

    # 维护每个交换机和路由器的端口计数器
    switchorrouter_port_count = {}

    # Convert hosts
    for host in xml_topo.hosts:
        node = GraphNode(host.name, host.os, 'host')
        json_topo.add_node(node)

        veth = GraphVeth(f"{host.name}-eth0", host.name, host.ip, host.gateway)
        json_topo.add_veth(veth)

    # Convert switches
    switchs = set()
    for switch in xml_topo.switches:
        node = GraphNode(switch.name, switch.name, 'switch')
        json_topo.add_node(node)
        switchs.add(switch.name)

        switchorrouter_port_count[switch.name] = 0

        for i in range(1, int(switch.ports) + 1):
            veth = GraphVeth(f"{switch.name}-eth{i}", switch.name)
            json_topo.add_veth(veth)

    # Convert routers
    routers = set()
    for router in xml_topo.routers:
        routers.add(router.name)
        if isinstance(router, UserFirewall):
            node = GraphNode(router.name, router.name, 'router', router.ports[0]['routing'], router.rules)
        else:
            node = GraphNode(router.name, router.name, router.category, router.ports[0]['routing'])
        json_topo.add_node(node)

        switchorrouter_port_count[router.name] = 0

        for port in router.ports:
            veth = GraphVeth(f"{router.name}-{port['name']}", router.name, port['ip'])
            json_topo.add_veth(veth)

    for router in xml_topo.routers:
        endpoint = set()
        for port in router.ports:
            if port['switcher'] is None or port['switcher'] == '' or port['switcher'] == ' ': continue
            if port['switcher'] not in endpoint:
                endpoint.add(port['switcher'])
            else:
                continue
            if port['switcher'] in routers:
                for router0 in xml_topo.routers:
                    if router0.name == port['switcher']:
                        for port0 in router0.ports:
                            if router.name == port0['switcher']:
                                switchorrouter_port_count[router.name] += 1
                                switchorrouter_port_count[router0.name] += 1
                                edge = GraphEdge(router.name, router0.name, f"{router.name}-{port['name']}",
                                                 f"{router0.name}-{port0['name']}")
                                json_topo.add_edge(edge)
            else:
                switchorrouter_port_count[port['switcher']] += 1
                switchorrouter_port_count[router.name] += 1
                edge = GraphEdge(port['switcher'], router.name,
                                 f"{port['switcher']}-eth{switchorrouter_port_count[port['switcher']]}",
                                 f"{router.name}-{port['name']}")
                json_topo.add_edge(edge)

    # for i in range(len(xml_topo.routers) - 1):
    #     router_port_count[xml_topo.routers[i].name] += 1
    #     router_port_count[xml_topo.routers[i + 1].name] += 1
    #     edge = GraphEdge(xml_topo.routers[i].name, xml_topo.routers[i + 1].name,
    #                      f"{xml_topo.routers[i].name}-eth{router_port_count[xml_topo.routers[i].name]}",
    #                      f"{xml_topo.routers[i + 1].name}-eth{router_port_count[xml_topo.routers[i + 1].name]}")
    #     json_topo.add_edge(edge)

    for switch in xml_topo.switches:
        for cascade in switch.cascading:
            if cascade == '':
                continue
            switchorrouter_port_count[switch.name] += 1
            switchorrouter_port_count[cascade] += 1
            edge = GraphEdge(switch.name, cascade, f"{switch.name}-eth{switchorrouter_port_count[switch.name]}",
                             f"{cascade}-eth{switchorrouter_port_count[cascade]}")
            json_topo.add_edge(edge)

    for host in xml_topo.hosts:
        if host.switcher in routers:
            for router in xml_topo.routers:
                if router.name == host.switcher:
                    for port in router.ports:
                        if host.gateway == port['ip'].split('/')[0]:
                            switchorrouter_port_count[host.switcher] += 1
                            edge = GraphEdge(host.name, host.switcher, f"{host.name}-eth0",
                                             f"{host.switcher}-{port['name']}")
                            json_topo.add_edge(edge)
        else:
            switchorrouter_port_count[host.switcher] += 1
            edge = GraphEdge(host.name, host.switcher, f"{host.name}-eth0",
                             f"{host.switcher}-eth{switchorrouter_port_count[host.switcher]}")
            json_topo.add_edge(edge)

    unique_edges = {}
    for edge in json_topo.edges:
        if edge.hash not in unique_edges:
            unique_edges[edge.hash] = edge

    json_topo.edges.clear()
    json_topo.edges.update(unique_edges.values())

    return json_topo


def is_same_subnet(ip1, ip2):
    ip1, mask1 = ip1.split('/')
    ip2, mask2 = ip2.split('/')

    ip1_bin = ''.join([bin(int(x) + 256)[3:] for x in ip1.split('.')])
    mask1_bin = '1' * int(mask1) + '0' * (32 - int(mask1))

    ip2_bin = ''.join([bin(int(x) + 256)[3:] for x in ip2.split('.')])
    mask2_bin = '1' * int(mask2) + '0' * (32 - int(mask2))

    subnet1 = ''.join([str(int(a) & int(b)) for a, b in zip(ip1_bin, mask1_bin)])
    subnet2 = ''.join([str(int(a) & int(b)) for a, b in zip(ip2_bin, mask2_bin)])

    return subnet1 == subnet2
