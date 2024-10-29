import json
import tarfile

import yaml
from nornir import InitNornir
from nornir_paramiko.plugins.tasks import paramiko_command, paramiko_sftp

from configuration import config_dir
from configuration.docker import docker_config_dir
from configuration.incus import incus_config_dir
from configuration.inventory import hosts_config_dir
from configuration.k3s import k3s_config_dir
from configuration.system import os_config_dir
from image import image_dir


class NornirHandler:
    def __init__(self):
        self.nr = InitNornir(
            inventory={
                "plugin": "SimpleInventory",
                "options": {
                    "host_file": f"{hosts_config_dir}/hosts.yaml",
                },
            }, )

    def run_install_docker(self):
        self.nr.run(task=install_docker)

    def run_raise_registry(self):
        self.nr.run(task=raise_local_image_regisrty)

    def run_install_incus(self):
        self.nr.run(task=install_incus)

    def run_install_k3s_server(self):
        self.nr.run(task=install_k3s_server)

    def get_k3s_server_access(self):
        self.nr.run(task=get_k3s_server_access)

    def access_lxd_server(self):
        self.nr.run(task=access_incus_server)


def install_docker(task):
    task.run(task=paramiko_command, command="apt update")
    task.run(task=paramiko_command, command="apt install -y docker.io")
    task.run(task=paramiko_sftp, action="put", src=f"{docker_config_dir}/docker",
             dst="/etc/default/docker")
    task.run(task=paramiko_command, command="sudo systemctl enable docker")
    task.run(task=paramiko_command, command="sudo systemctl restart docker")


def raise_local_image_regisrty(task):
    task.run(task=paramiko_command, command="touch /tmp/hosts")
    task.run(task=paramiko_sftp, action="put", src=f"{os_config_dir}/localregistry.host", dst="/tmp/hosts")
    task.run(task=paramiko_command, command="cat /tmp/hosts | tee -a /etc/hosts")
    task.run(task=paramiko_command, command="touch /tmp/registry.tar")
    task.run(task=paramiko_sftp, action="put", src=f"{image_dir}/docker/registry.tar", dst="/tmp/registry.tar")
    task.run(task=paramiko_command, command="docker load -i /tmp/registry.tar")
    task.run(task=paramiko_command,
             command="sudo docker run -d -p 5000:5000 --restart always --name registry registry:2")


def install_incus(task):
    task.run(task=paramiko_command, command="apt update")
    task.run(task=paramiko_command, command="apt install -y incus")
    task.run(task=paramiko_command, command="touch /tmp/lxd.crt")
    task.run(task=paramiko_sftp, action="put", src=f"{incus_config_dir}/lxd.crt",
             dst="/tmp/lxd.crt")
    task.run(task=paramiko_command, command="touch /tmp/lxd-init.yaml")
    task.run(task=paramiko_sftp, action="put", src=f"{incus_config_dir}/lxd-init.yaml",
             dst="/tmp/lxd-init.yaml")
    task.run(task=paramiko_command, command="systemctl restart incus")
    task.run(task=paramiko_command, command="incus admin init --preseed < /tmp/lxd-init.yaml")
    task.run(task=paramiko_command, command="incus config trust add-certificate /tmp/lxd.crt")
    task.run(task=paramiko_command, command="systemctl restart incus")


def access_incus_server(task):
    task.run(task=paramiko_command, command="touch /tmp/lxd.crt")
    task.run(task=paramiko_sftp, action="put", src=f"{incus_config_dir}/lxd.crt",
             dst="/tmp/lxd.crt")
    task.run(task=paramiko_command, command="lxc config trust add /tmp/lxd.crt")


def install_k3s_server(task):
    task.run(task=paramiko_command, command="echo 127.0.0.1        localregistry >> /etc/hosts")
    task.run(task=paramiko_command, command="mkdir -p /opt/k3s/bin")
    task.run(task=paramiko_command, command="touch /opt/k3s/bin/k3s")
    task.run(task=paramiko_sftp, action="put", src=f"{image_dir}/k3s/k3s",
             dst="/opt/k3s/bin/k3s")
    task.run(task=paramiko_command, command="cp /opt/k3s/bin/k3s /usr/local/bin/k3s && chmod +x /usr/local/bin/k3s")
    task.run(task=paramiko_command, command="touch /opt/k3s/k3s-airgap.tar.gz")
    task.run(task=paramiko_sftp, action="put", src=f"{image_dir}/k3s/k3s-airgap-images-amd64.tar.gz",
             dst="/opt/k3s/k3s-airgap.tar.gz")
    task.run(task=paramiko_command, command="docker load -i /opt/k3s/k3s-airgap.tar.gz")
    with tarfile.open(f"{image_dir}/k3s/k3s-airgap-images-amd64.tar.gz", "r:gz") as image_file:
        image_file.extract("repositories", path=f"{image_dir}/k3s")
    with open(f"{image_dir}/k3s/repositories", "r") as imageinfo_file:
        imageinfos = json.loads(imageinfo_file.read())
    for repo, tags in imageinfos.items():
        for tag in tags.keys():
            if 'localregistry:5000' not in repo:
                if '/' in repo:
                    localrepo = 'localregistry:5000/'.join(repo.split('/')[-1])
                else:
                    localrepo = 'localregistry:5000/'.join(repo)
                task.run(task=paramiko_command, command=f"docker tag {repo}:{tag} {localrepo}:{tag}")
                task.run(task=paramiko_command, command=f"docker push {localrepo}:{tag}")
            else:
                task.run(task=paramiko_command, command=f"docker push {repo}:{tag}")
    task.run(task=paramiko_command, command="mkdir -p /etc/rancher/k3s")
    task.run(task=paramiko_command, command="touch /etc/rancher/k3s/{config.yaml,k3s.yaml,registries.yaml}")
    task.run(task=paramiko_sftp, action="put", src=f"{k3s_config_dir}/server_config.yaml",
             dst="/etc/rancher/k3s/config.yaml")
    task.run(task=paramiko_sftp, action="put", src=f"{k3s_config_dir}/k3s.yaml",
             dst="/etc/rancher/k3s/k3s.yaml")
    task.run(task=paramiko_sftp, action="put", src=f"{k3s_config_dir}/registries.yaml",
             dst="/etc/rancher/k3s/registries.yaml")
    task.run(task=paramiko_command, command="touch /etc/systemd/system/k3s.service")
    task.run(task=paramiko_sftp, action="put", src=f"{os_config_dir}/k3s.service",
             dst="/etc/systemd/system/k3s.service")
    task.run(task=paramiko_command, command="systemctl enable k3s.service --now")


def get_k3s_server_access(task):
    task.run(task=paramiko_sftp, action="get", dst=f"{k3s_config_dir}/node-token",
             src="/var/lib/rancher/k3s/server/node-token")
    task.run(task=paramiko_sftp, action="get", dst=f"{k3s_config_dir}/k3s-server-access.yaml",
             src="/etc/rancher/k3s/k3s.yaml")
    with open(f"{config_dir}/base.yaml", 'r+') as f:
        config = yaml.safe_load(f)
        with open(f"{k3s_config_dir}/node-token", "r") as NodeTokenFile:
            config['base']['NodeToken'] = NodeTokenFile.read().strip()
        f.seek(0)
        yaml.dump(config, f)
        f.truncate()

    with open(f"{k3s_config_dir}/kubernetes-access.yaml", 'r+') as af:
        config = yaml.safe_load(af)
        with open(f"{k3s_config_dir}/k3s-server-access.yaml", "r") as asf:
            nconfig = yaml.safe_load(asf)
            config['clusters'][0]['cluster']['certificate-authority-data'] = nconfig['clusters'][0]['cluster'][
                'certificate-authority-data']
            config['users'][0]['user']['client-certificate-data'] = nconfig['users'][0]['user'][
                'client-certificate-data']
            config['users'][0]['user']['client-key-data'] = nconfig['users'][0]['user']['client-key-data']
            af.seek(0)
            yaml.dump(config, af)
            af.truncate()
