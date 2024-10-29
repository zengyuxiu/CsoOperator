from kubernetes import client, config, utils
from base64 import b64decode
from configuration.k3s import k3s_config_dir
from net.topology import UserHost
from io import StringIO


class KubernetesClient:
    def __init__(self):
        config.load_config(config_file=f"{k3s_config_dir}/kubernetes-access.yaml")
        aApiClient = client.AppsV1Api()
        self.client = client.CoreV1Api(aApiClient)

    def ApplyConfigurationFile(self, file_obj):
        file_content = file_obj.read()
        yaml_content = StringIO(file_content)
        utils.create_from_yaml(client.ApiClient(), yaml_content)

    def ApplyConfigurationFile(self, file_obj):
        file_content = file_obj.read()
        yaml_content = StringIO(file_content)
    def get_node_Token(self):
        self.client = client.CoreV1Api()
        secret = self.client.read_namespaced_secret("k3s-serving", "kube-system")
        token = b64decode(secret.data["token"]).decode("utf-8")
        print(token)

    def list_pod_for_all_namespaces(self):
        self.client = client.CoreV1Api()
        ret = self.client.list_pod_for_all_namespaces(watch=False)
        for i in ret.items:
            print("%s\t%s\t%s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))

    def clean_topo(self, topo):
        for container in topo.hosts:
            if isinstance(container, UserHost):
                self.clean_node(container.name)

    def clean_node(self, node_name):
        self.client = client.CoreV1Api()

        # 使节点进入维护模式
        body = {
            "spec": {
                "unschedulable": True
            }
        }
        self.client.patch_node(node_name, body)

        pods = self.client.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}").items
        for pod in pods:
            if pod.metadata.owner_references:
                # 跳过由 Deployment、ReplicaSet、DaemonSet 等管理的 Pod
                continue
            try:
                self.client.create_namespaced_pod_eviction(
                    name=pod.metadata.name,
                    namespace=pod.metadata.namespace,
                    body={
                        "apiVersion": "policy/v1beta1",
                        "kind": "Eviction",
                        "metadata": {
                            "name": pod.metadata.name,
                            "namespace": pod.metadata.namespace
                        }
                    }
                )
            except client.rest.ApiException as e:
                if e.status == 404:
                    continue
                else:
                    raise

        self.client.delete_node(node_name)

    def create_deployment(self):
        self.client = client.AppsV1Api()
        deployment = client.V1Deployment(
            metadata=client.V1ObjectMeta(name="test-vulnerability"),
            spec=client.V1DeploymentSpec(
                replicas=1,
                selector=client.V1LabelSelector(
                    match_labels={"app": "test-vulnerability"}
                ),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={"app": "test-vulnerability"}
                    ),
                    spec=client.V1PodSpec(
                        host_network=True,
                        node_selector={"kubernetes.io/hostname": "host1"},
                        containers=[
                            client.V1Container(
                                name="test-demo",
                                image="localregistry:5000/struts2:v57",
                                ports=[client.V1ContainerPort(container_port=8080)]
                            )
                        ]
                    )
                )
            )
        )
        self.client.create_namespaced_deployment(namespace="default", body=deployment)
