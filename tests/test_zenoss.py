import unittest

from zenoss import Zenoss


TEST_HOST = 'http://sethmiller-wsl:7000'
TEST_USER = 'admin'
TEST_PASSWORD = 'password'
TEST_SERVERNAME = 'testhost.com'


class TestZenoss(unittest.TestCase):
    def setUp(self):
        self.api = Zenoss(TEST_HOST, TEST_USER, TEST_PASSWORD, debug=True)

    def test_get_devices(self):
        result = self.api.get_devices()
        self.assertTrue(result['success'])

    def test_get_events(self):
        result = self.api.get_events()
        self.assertTrue(type(result is list))
        self.assertTrue('count' in result[0])

    def test_add_device(self):
        result = self.api.add_device(TEST_SERVERNAME, '/Devices/Server/Linux')
        self.assertTrue(result['success'])

    def test_remove_device(self):
        result = self.api.remove_device(TEST_SERVERNAME)
        self.assertTrue(result['success'])

    def test_create_event_on_device(self):
        self.api.create_event_on_device(TEST_SERVERNAME, 'Error', 'This is just an error')

    def test_ack_event(self):
        events = self.api.get_events()
        if len(events) > 0:
            self.assertTrue(self.api.ack_event(events[0]['evid'])['success'])

    def test_close_event(self):
        events = self.api.get_events()
        if len(events) > 0:
            self.assertTrue(self.api.close_event(events[0]['evid'])['success'])


if __name__ == '__main__':
    unittest.main()
