'''
The current license for this version is the "MIT License" as described by the Open Source Initiative.

Copyright 2011 Seth Miller

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''

#Some of this is "stolen" from the api example provided by Zenoss.
#I mostly made additions and changed the naming convention

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


    def get_events(self, systems=None, count=2, limit=100, prod_state=1000):
        results = []

        data = dict(start=0, limit=limit, dir='DESC', sort='severity')
        data['params'] = dict(severity=[5,4,3,2], eventState=[0,1])

        #TODO make this take a prod state and get everything above that number
        data['params']['prodState'] = str(prod_state)

        if systems:            
            for system in systems:
                data['params']['Systems'] = system
                
                events = self._router_request('EventsRouter', 'query',
                                         [data])['result']['events']

                for event in events:
                    if int(event['count']) >= count:
                        results.append(event)

        return results
    

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


    def add_device(self, device_name, device_class, collector='localhost' ):  
        data = dict(deviceName=device_name, deviceClass=device_class,
                    title=device_name, collector=collector)
        
        return self._router_request('DeviceRouter', 'addDevice',
                                    [data])['result']


    def get_device_info(self, device_name):
        data = dict(uid=device_name)        
        result = self._router_request('DeviceRouter',
                                      'getInfo', [data])['result']

        if result['success']:
            return result['data']
        else:
            return None


    def move_device(self, device, container):
        '''takes the device name and container to move to        
        container can be a group, system, or location'''
        
        uid, hash = self._get_device_uid(device)
        data = dict(uids = [uid], hashcheck = hash, container = container)    
        result = self._router_request('DeviceRouter',
                                      'moveDevices', [data])['result']
        
        if result['success']:
            return True
        else:
            return None
        
        
    def remove_device(self, device, container):        
        uid, hash = self._get_device_uid(device)        
        data = dict(uids = [uid], uid = container,
                    hashcheck = hash, action="remove")
        
        result = self._router_request('DeviceRouter',
                                      'removeDevices', [data])['result']
        
        if result['success']:
            return True
        else:
            return None
        
    def delete_device(self, device):
        uid, hash = self._get_device_uid(device)        
        data = dict(uids = [uid],
                    hashcheck = hash, action="delete")

        result = self._router_request('DeviceRouter',
                                      'removeDevices', [data])['result']
        
        if result['success']:
            return True
        else:
            return None        