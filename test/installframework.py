import unittest
from deployment import NornirHandler


class TestNornir(unittest.TestCase):
    def testdockerInstall(self):
        nr = NornirHandler()
        nr.run_install_docker()

    def testregistryInstall(self):
        nr = NornirHandler()
        nr.run_raise_registry()

    def testIncusinstall(self):
        nr = NornirHandler()
        nr.run_install_incus()

    def testK3sServerInstall(self):
        nr = NornirHandler()
        nr.run_install_k3s_server()

    def testGetK3sServerNodeToken(self):
        nr = NornirHandler()
        nr.get_k3s_server_access()

    def testAccessLxdServer(self):
        nr = NornirHandler()
        nr.access_lxd_server()


if __name__ == '__main__':
    unittest.main()
