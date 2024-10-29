import unittest
from driver.docker.client import DockerClient


class DockerTestCase(unittest.TestCase):
    def testConnection(self):
        client = DockerClient()
        print(client.client.containers.list())
