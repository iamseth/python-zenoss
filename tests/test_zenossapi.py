from zenossapi import ZenossAPI
import unittest

TEST_HOST = 'http://sethmiller-wsl:7000'
TEST_USER = 'admin'
TEST_PASSWORD = 'releng'
TEST_SERVERNAME = "testhost.com"

class TestZenossAPI(unittest.TestCase):
    def setUp(self):
        self.api = ZenossAPI()
        self.api.connect(TEST_HOST, TEST_USER, TEST_PASSWORD)


    def test_get_devices(self):
        result = self.api.get_devices()
        self.assertTrue(result['success'])


    def test_get_events(self):
        result = self.api.get_events()
        self.assertTrue(type(result['events'] is list))


    def test_add_device(self):
        result = self.api.add_device(TEST_SERVERNAME, '/Devices/Server/Linux')
        self.assertTrue(result['success'])


    def test_remove_device(self):
        result = self.api.remove_device(TEST_SERVERNAME)
        self.assertTrue(result['success'])


    def test_create_event_on_device(self):
        self.api.create_event_on_device(TEST_SERVERNAME, 'Error', 'This is just an error')

if __name__ == '__main__':
    unittest.main()