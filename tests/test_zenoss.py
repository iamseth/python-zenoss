import unittest

import re
import logging
from zenoss import Zenoss
from httmock import HTTMock, urlmatch


TEST_SERVERNAME = 'testhost.com'

logging.basicConfig(level=logging.DEBUG)


def mocked_device_router(request):
    # TODO move this to text .json files in tests directory
    return {'status_code': 200, 'content': {
    'result': {'totalCount': 1, 'success': True, 'hash': '123', 'devices': [{'name': TEST_SERVERNAME, 'uid': '123'}]}}}


def mocked_evconsole_router(request):
    # TODO move this to text .json files in tests directory
    events = [{'count': 0, 'evid': {'success': True}}]
    return {'status_code': 200, 'content': {'result': {'totalCount': 1, 'success': True, 'events': events}}}


@urlmatch(path='.*router$')
def response_content(url, request):
    if re.search('device_router', url.path):
        return mocked_device_router(request)
    if re.search('evconsole_router', url.path):
        return mocked_evconsole_router(request)


class TestZenoss(unittest.TestCase):
    def setUp(self):
        self.api = Zenoss('http://zenoss:8080', 'admin', 'password')

    def test_get_devices(self):
        with HTTMock(response_content):
            result = self.api.get_devices()
            self.assertTrue(result['success'])

    def test_get_events(self):
        with HTTMock(response_content):
            result = self.api.get_events()
            self.assertTrue(type(result is list))
            self.assertTrue('count' in result[0])

    def test_add_device(self):
        with HTTMock(response_content):
            result = self.api.add_device(TEST_SERVERNAME, '/Devices/Server/Linux')
            self.assertTrue(result['success'])

    def test_remove_device(self):
        with HTTMock(response_content):
            result = self.api.remove_device(TEST_SERVERNAME)
            self.assertTrue(result['success'])

    def test_create_event_on_device(self):
        with HTTMock(response_content):
            self.api.create_event_on_device(TEST_SERVERNAME, 'Error', 'This is just an error')

    def test_ack_event(self):
        with HTTMock(response_content):
            events = self.api.get_events()
            if len(events) > 0:
                self.assertTrue(self.api.ack_event(events[0]['evid'])['success'])

    def test_close_event(self):
        with HTTMock(response_content):
            events = self.api.get_events()
            if len(events) > 0:
                self.assertTrue(self.api.close_event(events[0]['evid'])['success'])


if __name__ == '__main__':
    unittest.main()
