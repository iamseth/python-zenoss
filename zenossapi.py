import os
import json
import urllib
import urllib2
import logging as log

ROUTERS = {'MessagingRouter': 'messaging',
           'EventsRouter': 'evconsole',
           'ProcessRouter': 'process',
           'ServiceRouter': 'service',
           'DeviceRouter': 'device',
           'NetworkRouter': 'network',
           'TemplateRouter': 'template',
           'DetailNavRouter': 'detailnav',
           'ReportRouter': 'report',
           'MibRouter': 'mib',
           'ZenPackRouter': 'zenpack'}

class ZenossAPI():
    def __init__(self, debug=False):
        self.debug = debug
        if debug:
            self.log_level = log.DEBUG
        else:
            self.log_level = log.INFO

        self.log_file = '%s/zenossapi.log' % os.getcwd()

        log.basicConfig(filename=os.environ['HOME'] + '',
            format='%(asctime)s.%(msecs).03d - %(funcName)s - %(levelname)s: %(message)s',
            level=self.log_level,
            datefmt='%b %d %H:%M:%S')

    def connect(self, host, username, password):
        self.password = password
        self.username = username
        self.host = host
        self.req_count = 1

        self.urlOpener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        if self.debug: self.urlOpener.add_handler(urllib2.HTTPHandler(debuglevel=1))

        login_params = urllib.urlencode(dict(
            __ac_name=username,
            __ac_password=password,
            submitted='true',
            came_from=host + '/zport/dmd'))

        log.info('Connecting to %s as %s' % (host, username))
        self.urlOpener.open(host + '/zport/acl_users/cookieAuthHelper/login', login_params)

    def _router_request(self, router, method, data=None):
        if router not in ROUTERS:
            raise Exception('Router "' + router + '" not available.')

        req = urllib2.Request('%s/zport/dmd/%s_router' % (self.host, ROUTERS[router]))
        req.add_header('Content-type', 'application/json; charset=utf-8')

        req_data = json.dumps([dict(
            action=router,
            method=method,
            data=data,
            type='rpc',
            tid=self.req_count)])

        self.req_count += 1
        log.info('Making request to router %s with method %s' % (router, method))
        log.debug('Request data: ' % req_data)
        return json.loads(self.urlOpener.open(req, req_data).read())['result']

    def get_devices(self, deviceClass='/zport/dmd/Devices'):
        log.info('Getting all devices')
        return self._router_request('DeviceRouter', 'getDevices', data=[{'uid': deviceClass, 'params': {}}])

    def find_device(self, device_name):
        log.info('Finding device %s' % device_name)
        device = filter(lambda x: x['name'] == device_name, self.get_devices()['devices'])[0]
        if not device:
            log.error('Cannot locate device %s' % device_name)
            raise Exception('Cannot locate device %s' % device_name)
        else:
            log.info('%s found' % device_name)
            return device

    def get_events(self, device=None, limit=100, component=None, eventClass=None):
        data = dict(start=0, limit=limit, dir='DESC', sort='severity')
        data['params'] = dict(severity=[5, 4, 3, 2], eventState=[0, 1])
        if device: data['params']['device'] = device
        if component: data['params']['component'] = component
        if eventClass: data['params']['eventClass'] = eventClass
        log.info('Getting events for: %s' % data)
        return self._router_request('EventsRouter', 'query', [data])

    def add_device(self, device_name, device_class):
        log.info('Adding %s' % device_name)
        data = dict(deviceName=device_name, deviceClass=device_class)
        return self._router_request('DeviceRouter', 'addDevice', [data])

    def remove_device(self, device_name):
        log.info('Removing %s' % device_name)
        device = self.find_device(device_name)
        data = dict(uids=[device['uid']], hashcheck=device['hash'], action='delete')
        return self._router_request('DeviceRouter', 'removeDevices', [data])

    def move_device(self, device_name, container):
        log.info('Moving %s to %s' % (device_name, container))
        device = self.find_device(device_name)
        data = dict(uids=[device['uid']], hashcheck=device['hash'], target=container)
        return self._router_request('DeviceRouter', 'moveDevices', [data])

    def set_prod_state(self, device_name, prod_state):
        log.info('Setting prodState on %s to %s' % (device_name, prod_state))
        device = self.find_device(device_name)
        data = dict(uids=[device['uid']], prodState=prod_state, hashcheck=device['hash'])
        return self._router_request('DeviceRouter', 'setProductionState', [data])

    def set_maintenance(self, device_name):
        return self.set_prod_state(device_name, 300)

    def set_production(self, device_name):
        return self.set_prod_state(device_name, 1000)

    def change_event_state(self, event_id, state):
        log.info('Changing eventState on %s to %s' % (event_id, state))
        return self._router_request('EventsRouter', state, [{'evids': [event_id]}])

    def ack_event(self, event_id):
        return self.change_event_state(event_id, 'acknowledge')

    def close_event(self, event_id):
        return self.change_event_state(event_id, 'close')

    def create_event_on_device(self, device_name, severity, summary):
        log.info('Creating new event for %s with severity %s' % (device_name, severity))
        if severity not in ('Critical', 'Error', 'Warning', 'Info', 'Debug', 'Clear'):
            raise Exception('Severity %s is not valid.' % severity)
        data = dict(device=device_name, summary=summary, severity=severity, component='', evclasskey='', evclass='')
        return self._router_request('EventsRouter', 'add_event', [data])
