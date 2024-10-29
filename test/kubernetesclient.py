import unittest
from driver.kubernetes.client import KubernetesClient


class K8sClientTest(unittest.TestCase):
    def testCreateDeployment(self):
        client = KubernetesClient()
        client.create_deployment()

    def testGetToken(self):
        client = KubernetesClient()
        client.list_pod_for_all_namespaces()

    def testDeleteNode(self):
        client = KubernetesClient()
        client.clean_node('host8')