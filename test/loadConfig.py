import unittest
from configuration import config_dir,load_config


class configLoadTest(unittest.TestCase):
    def testLoadConfig(self):
        load_config()