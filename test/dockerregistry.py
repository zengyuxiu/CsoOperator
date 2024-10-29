import unittest
from driver.docker.registry import Registry, baserepo


class DockerRegistryTest(unittest.TestCase):
    def testListAlias(self):
        client = Registry("struts2")
        alias = client.list_alias()
        print(alias)

    def testListRepo(self):
        client = Registry()
        repo = client.list_repositories()
        print(repo)

    def testPushBlob(self):
        client = Registry("struts2")
        dgst = client.push_image("/tmp/s2.tar")
        print(dgst)