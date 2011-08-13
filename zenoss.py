import json
import urllib
import urllib2

ROUTERS = { 'MessagingRouter': 'messaging',
            'EventsRouter': 'evconsole',
            'ProcessRouter': 'process',
            'ServiceRouter': 'service',
            'DeviceRouter': 'device',
            'NetworkRouter': 'network',
            'TemplateRouter': 'template',
            'DetailNavRouter': 'detailnav',
            'ReportRouter': 'report',
            'MibRouter': 'mib',
            'ZenPackRouter': 'zenpack' }

class Zenoss():
    
    def __init__(self, host, username, password):
        ''''
        Initialize the API connection, log in, and store authentication cookie
        '''
        
        self.host = host
       
        self.urlOpener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        self.req_count = 1
    
        login_params = urllib.urlencode(dict(
                        __ac_name = username,
                        __ac_password = password,
                        submitted = 'true',
                        came_from = host + '/zport/dmd'))
        self.urlOpener.open(host + '/zport/acl_users/cookieAuthHelper/login',
                            login_params)


    def _router_request(self, router, method, data=[]):
        if router not in ROUTERS:
            raise Exception('Router "' + router + '" not available.')

        req = urllib2.Request(self.host + '/zport/dmd/' +
                              ROUTERS[router] + '_router')

        req.add_header('Content-type', 'application/json; charset=utf-8')

        req_data = json.dumps([dict(
                    action=router,
                    method=method,
                    data=data,
                    type='rpc',
                    tid=self.req_count)])

        self.req_count += 1

        # Submit the request and convert the returned JSON to objects
        return json.loads(self.urlOpener.open(req, req_data).read())


    def _get_device_uid(self, device_name):        
        '''finds the UID for a device'''

        data = dict(limit=500000000)
        devices = self._router_request('DeviceRouter', 'getDevices',
                                    [data])['result']
        
        for device in devices['devices']:
            if device['name'] == device_name:
                return (device['uid'], devices['hash'])

        #name not found I guess, return None
        return None


    def get_devices(self, deviceClass='/zport/dmd/Devices'):
        return self._router_request('DeviceRouter', 'getDevices',
                                    data=[{'uid': deviceClass}])['result']


    def get_events(self, device=None, component=None, eventClass=None):
        data = dict(start=0, limit=100, dir='DESC', sort='severity')
        data['params'] = dict(severity=[5,4,3,2], eventState=[0,1])

        if device: data['params']['device'] = device
        if component: data['params']['component'] = component
        if eventClass: data['params']['eventClass'] = eventClass

        return self._router_request('EventsRouter', 'query', [data])['result']


    def add_device(self, deviceName, deviceClass):
        data = dict(deviceName=deviceName, deviceClass=deviceClass)
        return self._router_request('DeviceRouter', 'addDevice', [data])


    def create_event_on_device(self, device, severity, summary):
        if severity not in ('Critical', 'Error', 'Warning', 'Info', 'Debug', 'Clear'):
            raise Exception('Severity "' + severity +'" is not valid.')

        data = dict(device=device, summary=summary, severity=severity,
                    component='', evclasskey='', evclass='')
        return self._router_request('EventsRouter', 'add_event', [data])


    def ack_event(self, event_id):
        '''acks an event ID'''
        data = {'evids': [event_id]}
        return self._router_request('EventsRouter', 'acknowledge',
                                    [data])['result']['success']


    def close_event(self, event_id):
        '''moves an event to history'''
        data = {'evids': [event_id]}
        
        return self._router_request('EventsRouter', 'close',
                                    [data])['result']['success']

        
    def set_maintenance(self, device):
        '''Puts the device name into maintenance mode to prevent alerts'''
        
        uid, hash = self._get_device_uid(device)        
        data = dict(uids=[uid], prodState=300, hashcheck=hash)
        
        return self._router_request('DeviceRouter', 'setProductionState',
                                    [data])['result']['success']


    def set_production(self, device):
        '''Puts the device name into production mode'''
        
        uid, hash = self._get_device_uid(device)        
        data = dict(uids=[uid], prodState=1000, hashcheck=hash)
        
        return self._router_request('DeviceRouter', 'setProductionState',
                                    [data])['result']['success']
        
    def send_event(self):
        pass
    
    
    def run_command(self):
        pass