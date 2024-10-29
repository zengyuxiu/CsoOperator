import pylxd
import yaml
from net.topology import UserTopology, UserFirewall, UserHost, UserRouter, UserSwitcher
from configuration.k3s import k3s_config_dir
from configuration.incus import incus_config_dir
from configuration import config_dir
from image import image_dir
import random

url = 'https://172.171.50.67:8443'
cert = (f'{incus_config_dir}/lxd.crt', f'{incus_config_dir}/lxd.key')
verify = False


class LXDManager:
    def __init__(self):
        with open(f"{config_dir}/base.yaml", 'r') as f:
            config = yaml.safe_load(f)
        self.client = pylxd.Client(endpoint=f"https://{config['base']['ServerIp']}:8443", cert=cert, verify=verify,
                                   project=config['base']['Project'])

    def import_image(self, image_file, alias):
        image = self.client.images.create(source=pylxd.image.ImageSource(filename=image_file),
                                          aliases=[alias])
        print(f"Imported image: {image_file} with alias: {alias}")

    def create_project(self, project_name):
        if self.client.projects.exists(name=project_name) is not True:
            self.client.projects.create(name=project_name, description='')

    def delete_instance(self, instance_name):
        if self.client.instances.exists(instance_name):
            instance = self.client.instances.get(instance_name)
            instance.stop(wait=True)
            instance.delete(wait=True)

    def delete_network(self, network_name):
        if self.client.networks.exists(network_name):
            network = self.client.networks.get(network_name)
            network.delete(wait=True)

    def createManageBr(self):
        # self.client.networks.create("ManageBr",
        #                             {"ipv4.address": "110.0.0.0/8",
        #                              "ipv4.nat": "true",
        #                              "ipv4.dhcp": "true"})
        if self.client.networks.exists(name='ManageBr'):
            return
        self.client.networks.create(name="ManageBr", description="Manage Bridge", type="bridge",
                                    config={"ipv4.address": "110.254.254.254/8",
                                            "ipv4.nat": "true",
                                            "ipv6.address": None,
                                            "ipv6.nat": "false"})
        print(f"Created network: ManageBr with IP range: 110.0.0.0/8")

    def createSwitcher(self, network_name, ManageIp):
        # self.client.networks.create(network_name,
        #                             {"ipv4.address": ManageIp,
        #                              "ipv4.nat": "true",
        #                              "ipv4.dhcp": "true"})
        if self.client.networks.exists(network_name):
            return
        self.client.networks.create(name=network_name, description=network_name, type="bridge",
                                    config={"ipv4.address": ManageIp,
                                            "ipv4.nat": "true",
                                            "ipv6.address": None,
                                            "ipv6.nat": "False"})
        print(f"Created network: {network_name}with IP range: {ManageIp}")

    def createHost(self, HostName, IpAddress, SwitchName):
        with open(f"{k3s_config_dir}/agent_config.yaml", "r+") as file:
            config = yaml.safe_load(file)
            config["node-name"] = HostName
            file.seek(0)
            yaml.dump(config, file)
            file.truncate()

        devices = {"eth1": {"type": "nic",
                            "nictype": "bridged",
                            "parent": SwitchName,
                            "name": "eth1"},
                   "manage0": {"type": "nic",
                               "nictype": "bridged",
                               "parent": "ManageBr",
                               "name": "manage0"}}

        config = {"name": HostName,
                  "devices": devices,
                  "linux.kernel_modules": "ip_tables, ip6_tables, netlink_diag, nf_nat, overlay, br_netfilter",
                  "raw.lxc": "lxc.mount.auto = proc:rw   sys: rw",
                  "security.nesting": "true",
                  "security.privileged": "true",
                  "source": {"type": "image",
                             "alias": "debian-bookworm"}}

        instance = self.client.instances.create(config, wait=True)
        instance.start(wait=True)
        systemctlScript = f"""[Unit]
Description=K3s Agent Service
After=network.target

[Service]
Type=forking
ExecStart=/etc/rancher/k3s/start.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
        """
        startScript = f"""#!/bin/bash
ip addr add 192.163.3.34/24 dev eth1
ip addr add 110.130.42.190/8 dev manage0 
ip route add default via 110.254.254.254 dev manage0
# echo 110.254.254.254 localregistry>> /etc/hosts
ln -s /dev/console /dev/kmsg
nohup k3s agent &> /var/log/k3s.log &"""
        instance.execute(["mkdir", "-p", "/etc/rancher/k3s"])
        with open(f"{k3s_config_dir}/agent_config.yaml") as k3sConfigFile:
            instance.files.put("/etc/rancher/k3s/config.yaml", k3sConfigFile.read().encode())
        with open(f"{k3s_config_dir}/registries.yaml") as registriesConfigFile:
            instance.files.put("/etc/rancher/k3s/registries.yaml", registriesConfigFile.read().encode())
        with open(f"{image_dir}/k3s/k3s", "rb") as k3sBinFile:
            instance.files.put("/usr/local/bin/k3s", k3sBinFile)
        hostinfo = """110.254.254.254    localregistry"""
        instance.files.put("/etc/hosts", hostinfo)
        instance.execute(["chmod", "+x", "/usr/local/bin/k3s"])
        instance.files.put("/etc/rancher/k3s/start.sh", startScript)
        instance.execute(["chmod", "+x", "/etc/rancher/k3s/start.sh"])
        instance.files.put("/etc/systemd/system/k3s-agent.service", systemctlScript)
        instance.execute(["systemctl", "enable", "k3s-agent", "--now"])
        print(f"Created and started container: Host")
        return

    def add_virtualization_support(self):
        default_profile = self.client.profiles.get('default')

        default_profile.config.update({
            "linux.kernel_modules": "ip_tables, ip6_tables, netlink_diag, nf_nat, overlay, br_netfilter",
            "raw.lxc": "lxc.mount.auto = proc:rw sys:rw",
            "security.nesting": "true",
            "security.privileged": "true"
        })

        default_profile.save()

    def createRouter(self, RouterName, Interfaces):
        return

    def create_and_configure_containers(self, container_name, network_name):
        devices = {"eth0": {"type": "nic",
                            "nictype": "bridged",
                            "parent": "net4",
                            "name": "eth1",
                            "ipv4.address": f"10.4.4.{container_name[1:]}/24"},
                   "manage0": {"type": "nic",
                               "nictype": "bridged",
                               "parent": "mbr",
                               "name": "manage0"}}

        config = {"name": container_name,
                  "devices": devices,

                  "source": {"type": "image",
                             "alias": "route"}}

        container = self.client.containers.create(config, wait=True)
        container.start(wait=True)
        print(f"Created and started container: {container_name}")

        container.files.get("/root/vnf-broker.yaml").replace("node_name", container_name)
        container.execute(["sed", "-i", f"s/node_name/{container_name}/g", "/root/vnf-broker.yaml"])
        container.execute(["ln -s /dev/console /dev/kmsg"])
        print(f"Modified vnf-broker config and restarted service for container: {container_name}")

    def configure_ospf(self, container_names, network_names, ip_ranges):
        for i in range(1, 4):
            container_name = f"R{i}"
            container = self.client.containers.get(container_name)
            container.files.put("/etc/frr/ospfd.conf", f"router ospf\nrouter-id {container_name}\n")
            for network_name, ip_range in zip(network_names, ip_ranges):
                container.execute(["bash", "-c", f"echo 'network {ip_range} area 0' >> /etc/frr/ospfd.conf"])
            container.execute(["/etc/init.d/frr", "restart"])
            print(f"Configured OSPF for container: {container_name}")

    def run(self):
        CONTAINER_NAMES = ["R1", "R2", "R3", "h1", "h2", "h3"]
        NETWORK_NAMES = ["net1", "net2", "net3", "net4"]
        IP_RANGES = ["10.1.1.1/24", "10.2.2.1/24", "10.3.3.1/24", "10.4.4.1/24"]

        self.import_image("route.tar.gz", "route")
        self.create_and_configure_containers(CONTAINER_NAMES, NETWORK_NAMES)
        self.configure_ospf(CONTAINER_NAMES, NETWORK_NAMES, IP_RANGES)

    def deploy(self, topo):
        self.add_virtualization_support()
        self.createManageBr()
        for switcher in topo.switches:
            if isinstance(switcher, UserSwitcher):
                self.createSwitcher(switcher.name, switcher.mgmt_ip)
        for container in topo.hosts:
            if isinstance(container, UserHost):
                self.createHost(container.name, container.ip, container.switcher)
        for router in topo.routers:
            if isinstance(router, UserRouter):
                self.createRouter(router.name, router.ports)

    def destroy(self, topo):
        for container in topo.hosts:
            if isinstance(container, UserHost):
                self.delete_instance(container.name)
        for switcher in topo.switches:
            if isinstance(switcher, UserSwitcher):
                self.delete_network(network_name=switcher.name)


def generate_random_ip():
    first_octet = 110

    second_octet = random.randint(2, 253)
    third_octet = random.randint(2, 253)
    fourth_octet = random.randint(2, 253)

    ip_address = f"{first_octet}.{second_octet}.{third_octet}.{fourth_octet}"

    return ip_address
