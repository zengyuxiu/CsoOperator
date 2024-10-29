import unittest
from driver.lxd import lxd


class TestClient(unittest.TestCase):
    def testConnection(self):
        client = lxd.LXDManager()
        container = client.client.instances.all()
        print(container)

    def testDeleteInstance(self):
        client = lxd.LXDManager()
        inst = client.client.instances.get("host2")
        inst.stop(wait=True)
        inst.delete(wait=True)

    def testAddInstanceK3sAgent(self):
        client = lxd.LXDManager()
        client.add_k3s_agent_support()

    def testaddvSupport(self):
        client = lxd.LXDManager()
        client.add_virtualization_support()


if __name__ == '__main__':
    unittest.main()
