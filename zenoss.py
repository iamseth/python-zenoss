'''Python module to work with the Zenoss JSON API
'''
import ast
import re
import json
import logging
import requests

log = logging.getLogger(__name__) # pylint: disable=C0103
requests.packages.urllib3.disable_warnings()

ROUTERS = {'MessagingRouter': 'messaging',
           'EventsRouter': 'evconsole',
           'EventClassesRouter': 'Events/evclasses',
           'ProcessRouter': 'process',
           'ServiceRouter': 'service',
           'DeviceRouter': 'device',
           'ManufacturersRouter': 'manufacturers',
           'NetworkRouter': 'network',
           'PropertiesRouter': 'properties',
           'TemplateRouter': 'template',
           'DetailNavRouter': 'detailnav',
           'ReportRouter': 'report',
           'MibRouter': 'mib',
           'TriggersRouter': 'triggers',
           'ZenPackRouter': 'zenpack'}


class ZenossException(Exception):
    '''Custom exception for Zenoss
    '''
    pass


class Zenoss(object):
    '''A class that represents a connection to a Zenoss server
    '''
    def __init__(self, host, username, password, ssl_verify=True):
        self.__host = host
        self.__session = requests.Session()
        self.__session.auth = (username, password)
        self.__session.verify = ssl_verify
        self.__req_count = 0

    def __router_request(self, router, method, data=None, uri=None):
        '''Internal method to make calls to the Zenoss request router
        '''
        if router not in ROUTERS:
            raise ZenossException('Router "' + router + '" not available.')

        req_data = json.dumps([dict(
            action=router,
            method=method,
            data=data,
            type='rpc',
            tid=self.__req_count)])
        log.debug('Making request to router %s with method %s', router, method)
        if not uri:
            uri = '%s/zport/dmd/%s_router' % (self.__host, ROUTERS[router])
        headers = {'Content-type': 'application/json; charset=utf-8'}
        response = self.__session.post(uri, data=req_data, headers=headers)
        self.__req_count += 1

        # The API returns a 200 response code even whe auth is bad.
        # With bad auth, the login page is displayed. Here I search for
        # an element on the login form to determine if auth failed.
        if re.search('name="__ac_name"', response.content.decode("utf-8")):
            log.error('Request failed. Bad username/password.')
            raise ZenossException('Request failed. Bad username/password.')
        if response.status_code == 200:
            return json.loads(response.content.decode("utf-8"))['result']
        else:
            raise ZenossException("Unable to complete request:\n%s\nHTTP Status: %s" % (
                req_data,
                response.status_code,
            ))

    def get_rrd_values(self, device, dsnames, start=None, end=None, function='LAST'): # pylint: disable=R0913
        '''Method to abstract the details of making a request to the getRRDValue method for a device
        '''
        if function not in ['MINIMUM', 'AVERAGE', 'MAXIMUM', 'LAST']:
            raise ZenossException('Invalid RRD function {0} given.'.format(function))

        if len(dsnames) == 1:
            # Appending a junk value to dsnames because if only one value is provided Zenoss fails to return a value.
            dsnames.append('junk')

        url = '{0}/{1}/getRRDValues'.format(self.__host, self.device_uid(device))
        params = {'dsnames': dsnames, 'start': start, 'end': end, 'function': function}
        return ast.literal_eval(self.__session.get(url, params=params).content)

    def get_devices(self, device_class='/zport/dmd/Devices', limit=None):
        '''Get a list of all devices.

        '''
        log.info('Getting all devices')
        return self.__router_request('DeviceRouter', 'getDevices',
                                     data=[{'uid': device_class, 'params': {}, 'limit': limit}])

    def get_components(self, device_name, **kwargs):
        '''Get components for a device given the name
        '''
        uid = self.device_uid(device_name)
        return self.get_components_by_uid(uid=uid, **kwargs)

    def get_components_by_uid(self, uid=None, meta_type=None, keys=None,
                              start=0, limit=50, page=0,
                              sort='name', dir='ASC', name=None):
        '''Get components for a device given the uid
        '''
        data = dict(uid=uid, meta_type=meta_type, keys=keys, start=start,
                    limit=limit, page=page, sort=sort, dir=dir, name=name)
        return self.__router_request('DeviceRouter', 'getComponents', [data])

    def find_device(self, device_name):
        '''Find a device by name.

        '''
        log.info('Finding device %s', device_name)
        all_devices = self.get_devices()

        try:
            device = [d for d in all_devices['devices'] if d['name'] == device_name][0]
            # We need to save the has for later operations
            device['hash'] = all_devices['hash']
            log.info('%s found', device_name)
            return device
        except IndexError:
            log.error('Cannot locate device %s', device_name)
            raise Exception('Cannot locate device %s' % device_name)

    def device_uid(self, device):
        '''Helper method to retrieve the device UID for a given device name
        '''
        return self.find_device(device)['uid']

    def add_device(self, device_name, device_class, collector='localhost'):
        '''Add a device.

        '''
        log.info('Adding %s', device_name)
        data = dict(deviceName=device_name, deviceClass=device_class, model=True, collector=collector)
        return self.__router_request('DeviceRouter', 'addDevice', [data])

    def remove_device(self, device_name):
        '''Remove a device.

        '''
        log.info('Removing %s', device_name)
        device = self.find_device(device_name)
        data = dict(uids=[device['uid']], hashcheck=device['hash'], action='delete')
        return self.__router_request('DeviceRouter', 'removeDevices', [data])

    def move_device(self, device_name, organizer):
        '''Move the device the organizer specified.

        '''
        log.info('Moving %s to %s', device_name, organizer)
        device = self.find_device(device_name)
        data = dict(uids=[device['uid']], hashcheck=device['hash'], target=organizer)
        return self.__router_request('DeviceRouter', 'moveDevices', [data])

    def set_prod_state(self, device_name, prod_state):
        '''Set the production state of a device.

        '''
        log.info('Setting prodState on %s to %s', device_name, prod_state)
        device = self.find_device(device_name)
        data = dict(uids=[device['uid']], prodState=prod_state, hashcheck=device['hash'])
        return self.__router_request('DeviceRouter', 'setProductionState', [data])

    def set_maintenance(self, device_name):
        '''Helper method to set prodState for device so that it does not alert.

        '''
        return self.set_prod_state(device_name, 300)

    def set_production(self, device_name):
        '''Helper method to set prodState for device so that it is back in production and alerting.

        '''
        return self.set_prod_state(device_name, 1000)

    def set_product_info(self, device_name, hw_manufacturer, hw_product_name, os_manufacturer, os_product_name): # pylint: disable=R0913
        '''Set ProductInfo on a device.

        '''
        log.info('Setting ProductInfo on %s', device_name)
        device = self.find_device(device_name)
        data = dict(uid=device['uid'],
                    hwManufacturer=hw_manufacturer,
                    hwProductName=hw_product_name,
                    osManufacturer=os_manufacturer,
                    osProductName=os_product_name)
        return self.__router_request('DeviceRouter', 'setProductInfo', [data])

    def set_rhel_release(self, device_name, release):
        '''Sets the proper release of RedHat Enterprise Linux.'''
        if type(release) is not float:
            log.error("RHEL release must be a float")
            return {u'success': False}
        log.info('Setting RHEL release on %s to %s', device_name, release)
        device = self.find_device(device_name)
        return self.set_product_info(device_name, device['hwManufacturer']['name'], device['hwModel']['name'], 'RedHat',
                                     'RHEL {}'.format(release))

    def set_device_info(self, device_name, data):
        '''Set attributes on a device or device organizer.
            This method accepts any keyword argument for the property that you wish to set.

        '''
        data['uid'] = self.find_device(device_name)['uid']
        return self.__router_request('DeviceRouter', 'setInfo', [data])

    def remodel_device(self, device_name):
        '''Submit a job to have a device remodeled.

        '''
        return self.__router_request('DeviceRouter', 'remodel', [dict(uid=self.find_device(device_name)['uid'])])

    def set_collector(self, device_name, collector):
        '''Set collector for device.

        '''
        device = self.find_device(device_name)
        data = dict(uids=[device['uid']], hashcheck=device['hash'], collector=collector)
        return self.__router_request('DeviceRouter', 'setCollector', [data])

    def rename_device(self, device_name, new_name):
        '''Rename a device.

        '''
        data = dict(uid=self.find_device(device_name)['uid'], newId=new_name)
        return self.__router_request('DeviceRouter', 'renameDevice', [data])

    def reset_ip(self, device_name, ip_address=''):
        '''Reset IP address(es) of device to the results of a DNS lookup or a manually set address.

        '''
        device = self.find_device(device_name)
        data = dict(uids=[device['uid']], hashcheck=device['hash'], ip=ip_address)
        return self.__router_request('DeviceRouter', 'resetIp', [data])

    def get_events(self, device=None, limit=100, component=None,
                   severity=None, event_class=None, start=0,
                   event_state=None, sort='severity', direction='DESC'):
        '''Find current events.
             Returns a list of dicts containing event details. By default
             they are sorted in descending order of severity.  By default,
             severity {5, 4, 3, 2} and state {0, 1} are the only events that
             will appear.

        '''
        if severity is None:
            severity = [5, 4, 3, 2]
        if event_state is None:
            event_state = [0, 1]
        data = dict(start=start, limit=limit, dir=direction, sort=sort)
        data['params'] = dict(severity=severity, eventState=event_state)
        if device is not None:
            data['params']['device'] = device
        if component is not None:
            data['params']['component'] = component
        if event_class is not None:
            data['params']['eventClass'] = event_class
        log.info('Getting events for %s', data)
        return self.__router_request(
            'EventsRouter', 'query', [data])['events']

    def get_event_detail(self, event_id):
        '''Find specific event details

        '''
        data = dict(evid=event_id)
        return self.__router_request('EventsRouter', 'detail', [data])

    def write_log(self, event_id, message):
        '''Write a message to the event's log

        '''
        data = dict(evid=event_id, message=message)
        return self.__router_request('EventsRouter', 'write_log', [data])

    def change_event_state(self, event_id, state):
        '''Change the state of an event.

        '''
        log.info('Changing eventState on %s to %s', event_id, state)
        return self.__router_request('EventsRouter', state, [{'evids': [event_id]}])

    def ack_event(self, event_id):
        '''Helper method to set the event state to acknowledged.

        '''
        return self.change_event_state(event_id, 'acknowledge')

    def close_event(self, event_id):
        '''Helper method to set the event state to closed.

        '''
        return self.change_event_state(event_id, 'close')

    def create_event_on_device(self, device_name, severity, summary,
                               component='', evclasskey='', evclass=''):
        '''Manually create a new event for the device specified.

        '''
        log.info('Creating new event for %s with severity %s', device_name, severity)
        if severity not in ('Critical', 'Error', 'Warning', 'Info', 'Debug', 'Clear'):
            raise Exception('Severity %s is not valid.' % severity)
        data = dict(device=device_name, summary=summary, severity=severity,
                    component=component, evclasskey=evclasskey, evclass=evclass)
        return self.__router_request('EventsRouter', 'add_event', [data])

    def get_load_average(self, device):
        '''Returns the current 1, 5 and 15 minute load averages for a device.
        '''
        dsnames = ('laLoadInt1_laLoadInt1', 'laLoadInt5_laLoadInt5', 'laLoadInt15_laLoadInt15')
        result = self.get_rrd_values(device=device, dsnames=dsnames)
        def normalize_load(load):
            '''Convert raw RRD load average to something reasonable so that it matches output from /proc/loadavg'''
            return round(float(load) / 100.0, 2)
        return [normalize_load(l) for l in result.values()]

    def add_device_class(self, name, description="", path=""):
        '''
        create a new device class in zenoss
        zen.add_device_class("Arista", path="/Network")
        :param name: name of new device class
        :type name: string
        :param description: description of new device class
        :type description: string
        :return: dict showing the status of the command
        :rtype: dict
        usage::
            >>> zen.add_device_class("Testing", path="/HTTP")
            {u'msg': u'Device Class Added',
            u'nodeConfig': {
                u'children': [],
                u'hasNoGlobalRoles': False,
                u'hidden': False,
                u'iconCls': u'tree-severity-icon-small-clear',
                u'id': u'.zport.dmd.Devices.HTTP.Testing',
                u'leaf': False,
                u'path': u'Devices/HTTP/Testing',
                u'text': {u'count': 0, u'description': u'devices', u'text': u'Testing'},
                u'uid': u'/zport/dmd/Devices/HTTP/Testing',
                u'uuid': u'...',
                u'zPythonClass': u''},
            u'success': True}
        '''
        base_org = "/zport/dmd/Devices%s" % path
        data = dict(contextUid=base_org, id=name, description=description, type="organizer")
        return self.__router_request('DeviceRouter', 'addDeviceClassNode', [data])

    def add_event_class(self, name, description="", path=""):
        '''
        create a new event class

        :param name: the endpoint name of the event class
        :type name: string
        :param description: description the new event class
        :type description: string
        :param path: path to where to put new event class
        :type path: string
        :return: zenoss success dict, with nodeConfig key showing the new event class details
        :rtype: dict

        usage::
            >>> zen.add_event_class("Test", path="/Net", description="Testing")
            {u'nodeConfig': {u'children': [],
                 u'count': 0,
                 u'hidden': False,
                 u'iconCls': u'tree-severity-icon-small-clear',
                 u'id': u'.zport.dmd.Events.Net.Testing',
                 u'leaf': True,
                 u'path': u'Events/Net/Test',
                 u'text': {u'count': 0,
                 u'description': u'Testing',
                 u'hasTransform': False,
                 u'text': u'Testing'},
                 u'uid': u'/zport/dmd/Events/Net/Testing',
                 u'uuid': u'...'},
             u'success': True}
        '''
        base_org = "/zport/dmd/Events%s" % path
        data = dict(contextUid=base_org, id=name, description=description, type="organizer")
        return self.__router_request('EventClassesRouter', 'addNode', [data])

    def add_group(self, group, description="", path=""):
        '''
        add group

        :param group: name of group to be added
        :type group: string
        :param description: description for the group
        :type description: string
        :param path: path to the group, if group is to be placed in suborganizers
        :type path: string
        :return: zenoss success dict
        :rtype: dict

        usage::
            >>> zen.add_group("MyGroup")
            {u'nodeConfig': {u'children': [],
                u'hasNoGlobalRoles': False,
                u'hidden': False,
                u'iconCls': u'tree-severity-icon-small-clear',
                u'id': u'.zport.dmd.Groups.MyGroup',
                u'leaf': False,
                u'path': u'Groups/MyGroup',
                u'text': {u'count': 0, u'description': u'devices', u'text': u'MyGroup'},
                u'uid': u'/zport/dmd/Groups/MyGroup',
                u'uuid': u'...',
                u'zPythonClass': None},
            u'success': True
        '''
        log.info('Adding Group %s', group)
        base_org = "/zport/dmd/Groups/%s" % path
        data = dict(type='organizer', contextUid=base_org, id=group, description=description)
        return self.__router_request('DeviceRouter', 'addNode', [data])

    def add_hardware_product(self, product_name, manufacturer, product_type, part_number="",
                             product_keys="", description=""):
        '''
        Add Hardware
        '''
        log.info('Adding Hardware Product %s', product_name)
        tmp = dict(prodname=product_name, uid="/zport/dmd/Manufacturers/%s" % manufacturer,
                   type=product_type, description=description, partno=part_number,
                   prodkeys=product_keys)
        data = dict(params=tmp)
        return self.__router_request('ManufacturersRouter', 'addNewProduct', [data])

    def add_location(self, location_name, path="", description="", address=""):
        '''
        Add Location

        path key word denotes the path under /Locations that should be added
        and should be formatted like this sub/sub1

        :param location_name: name of location
        :type location_name: string
        :param path: path to location organizer
        :type path: string
        :param description: description of location
        :type description: string
        :param address: address of location
        :type address: string
        :return: zenoss success dict
        :rtype: dict

        usage::
            >>> zen.add_location("Springfield", address="742 evergreen terrace")
            {u'msg': u'Location added',
             u'nodeConfig': {u'children': [],
              u'hasNoGlobalRoles': False,
              u'hidden': False,
              u'iconCls': u'tree-severity-icon-small-clear',
              u'id': u'.zport.dmd.Locations.Springfield',
              u'leaf': False,
              u'path': u'Locations/Springfield',
              u'text': {u'count': 0, u'description': u'devices', u'text': u'Springfield'},
              u'uid': u'/zport/dmd/Locations/Springfield',
              u'uuid': u'...',
              u'zPythonClass': None},
             u'success': True}
        '''
        log.info('Adding Location %s', location_name)
        base_org = "/zport/dmd/Locations%s" % path
        data = dict(type='organizer', contextUid=base_org, id=location_name, description=description,
                    address=address)
        return self.__router_request('DeviceRouter', 'addLocationNode', [data])

    def add_notification(self, name, action):
        '''
        add a new notification

        :param name: name of the notification
        :type name: string
        :param action: the notifications action
        :type action: string
        :return: zenoss success dict where the data key holds the whole notifications config details
        :rtype: dict
        usage::
            >>> zen.add_notification("Testing", "email")
            {u'data':
                {u'action': u'email',
                u'content': {...},
                  ...
                },
            u'success': True}
        '''
        data = dict(newId=name, action=action)
        return self.__router_request('TriggersRouter', 'addNotification', [data])

    def add_trigger(self, name, rules=None, users=None, enabled=True,
                    global_manage=False, global_read=False, global_write=False):
        '''
        add a new trigger

        :param name: name of new trigger
        :type name: string
        :param rule: event rule string
        :type rule: string
        :param users: list of dicts for user setting definitions
        :type rule: list
        :param enabled: is the trigger enabled
        :type enabled: boolean
        :param global_manage: is the trigger manageable by all, can it be deleted
        :type global_manage: boolean
        :param global_read: is the trigger readable by all, can it be seen
        :type gloabl_read: boolean
        :param global_write: is the trigger writable by all, can it be updated
        :type global_write: boolean
        :return: zenoss success dict
        :rtype: dict


        usage::
            >>> zen.add_trigger('TEST')
            {u'data': u'b0be2cf8-6182-4cc5-8b5c-545765869612', u'success': True}
        '''
        result = self.__router_request('TriggersRouter', 'addTrigger', [dict(newId=name)])
        if not result['success']:
            raise ZenossException("Unable to add trigger %s Reason: %s" % (name, result['msg']))
        if rules:
            update_result = self.update_trigger_rules(name, rules, users=users, enabled=enabled,
                                                      global_manage=global_manage,
                                                      global_read=global_read,
                                                      global_write=global_write)
            if not update_result['success']:
                raise ZenossException("Unable to update rules for trigger %s" % name)
        return result

    def get_locations(self, location='/zport/dmd/Locations', limit=None):
        '''
        given a location endpoint return the details of the location object

        :return: dict of dict, with locations key holding a list of dicts
        :rtype: dict
        ::
            >> zen.get_locations()
            {
                u'locations': [
                    {u'name': u'/DataCenter1'},
                ],
                u'success': True,
                u'totalCount': 1
            }
        '''
        return self.__router_request('DeviceRouter', 'getLocations',
                                     data=[{'uid': location, 'params': {}, 'limit': limit}])

    def get_groups(self, groups='/zport/dmd/Groups', limit=None):
        '''
        get details of infrastructure group
        '''
        return self.__router_request('DeviceRouter', 'getGroups',
                                     data=[{'uid': groups, 'params': {}, 'limit': limit}])

    def get_device_classes(self, path):
        '''
        given a device class path return all the sub classes

        :param path: path to device classes
        :type path: string
        :return: list of dicts where each dict describes the sub device class
        :rtype: list
        uasge::
            >>> zen.get_device_classes("/Network")
            [{
                u'hidden': False,
                u'iconCls': u'tree-severity-icon-small-clear',
                u'id': u'.zport.dmd.Devices.Network.Router',
                u'leaf': False,
                u'path': u'Devices/Network/Router',
                u'text': {u'count': 0, u'description': u'devices', u'text': u'Router'},
                u'uid': u'/zport/dmd/Devices/Network/Router'
            }]
        '''
        base_org = "/zport/dmd/Devices%s" % path
        return self.__router_request('DeviceRouter', 'asyncGetTree', [base_org])

    def get_device_class_template(self, path):
        '''
        gather the templates for a device class

        :param path: Path to the device class, the root is /Devices
        :type path: string
        :return: list of device class templates
        :rtype: list
        usage::
            >>> zen.get_device_class_template("/Network")
            [{u'id': u'/zport/dmd/Devices/rrdTemplates/Device',
            u'leaf': True,
            u'path': u'/',
            u'text': u'Device (/)',
            u'uid': u'/zport/dmd/Devices/rrdTemplates/Device'}]
        '''
        base_org = "/zport/dmd/Devices%s" % path
        return self.__router_request('DeviceRouter', 'getTemplates', [base_org])

    def get_ec_instance_details(self, name, path="", is_uid=False):
        '''
        get the details of an event class

        :param name: instance name
        :type name: string
        :param path: path to event class transform
        :type path: string
        :param is_uid: flag to check if name is uid
        :type is_uid: boolean
        :return: zenoss success dict, with data key holding all the instance details
        :rtype: dict


        usage::
            >>> zen.get_ec_instance_details("bgpBackwardTransNotification", path="/Net/BGP")
            {u'data': [{u'evaluation': u'',
                u'eventClass': u'BGP',
                u'eventClassKey': u'bgpNotification.2',
                u'example': u'snmp trap bgpNotification.2',
                u'id': u'bgpBackwardTransNotification',
                u'regex': u'',
                u'resolution': u'',
                u'rule': u'',
                u'sequence': 8,
                u'transform': u'\'\'\'\nevent transform for bgpBackwardTransition\n\'\'\'\n
                u'uid': u'/zport/dmd/Events/Net/BGP/instances/bgpBackwardTransNotification'}],
             u'success': True}
        '''
        if is_uid:
            data = dict(uid=name)
        else:
            data = dict(uid="/zport/dmd/Events%s/instances/%s" % (path, name))
        return self.__router_request('EventClassesRouter', 'getInstanceData', [data])

    def get_event_classes_instances(self, path=""):
        '''
        get all the event class instances

        :params path: limit the instances to event classes in this path
        :type path: string
        :return: zenoss success dict, with data key holding all the event classes
        :rtype: dict

        usage::
            >>> zen.get_event_classes(path="/Net/Time")
            {u'data': [{
                u'eval': u'The time provider NtpServer...',
               u'eventClassKey': u'W32Time_22',
               u'hasTransform': False,
               u'id': u'W32Time_22',
               u'uid': u'/zport/dmd/Events/Net/Time/instances/W32Time_22'}],
           u'success': True}
        '''
        base_org = "/zport/dmd/Events%s" % path
        data = dict(params={}, uid=base_org)
        return self.__router_request('EventClassesRouter', 'getInstances', [data])

    def get_ec_instance_transform(self, name, path="", is_uid=False):
        '''
        get the event transform off an event class instance

        :param name: instance name
        :type name: string
        :param path: path to event class transform
        :type path: string
        :param is_uid: flag to check if name is uid
        :type is_uid: boolean
        :return: zenoss success dict
        :rtype: dict

        usage::
            >>> zen.get_ec_instance_transform("bgpBackwardTransNotif", path="/Net/BGP")
            {
                u'data': u'\'\'\'\nevent transform for bgpBackwardTransNotif\n\'\'\'\n...',
                u'success': True
            }
        '''
        if is_uid:
            data = dict(uid=name)
        else:
            base_org = "/zport/dmd/Events%s" % path
            data = dict(uid="%s/instances/%s" % (base_org, name))
        return self.__router_request('EventClassesRouter', 'getTransform', [data])

    def get_location_details(self, name, path=""):
        '''
        given a location return all the info about said location

        :param name: location name
        :type name: string
        :param path: path to location
        :return: dict of dict where data key has all the location details
        :rtype: dict
        ::
            >>> zen.get_location_details("DataCenter1")
            {u'data': {u'address': u'742 Evergreen Terrace',
              u'description': u'',
              u'events': {u'clear': {u'acknowledged_count': 0, u'count': 0},
               u'critical': {u'acknowledged_count': 0, u'count': 1},
               u'debug': {u'acknowledged_count': 0, u'count': 0},
               u'error': {u'acknowledged_count': 1, u'count': 7},
               u'info': {u'acknowledged_count': 0, u'count': 82},
               u'warning': {u'acknowledged_count': 0, u'count': 8}},
              u'id': u'Europe',
              u'inspector_type': u'Location',
              u'meta_type': u'Location',
              u'name': u'/DataCenter1',
              u'severity': u'critical',
              u'uid': u'/zport/dmd/Locations/DataCenter1',
              u'uuid': u'...'},
             u'disabled': False,
             u'success': True}
        '''
        uid = "/zport/dmd/Locations%s/%s" % (path, name)
        return self.__router_request('DeviceRouter', 'getInfo', data=[dict(uid=uid)])

    def get_notifications(self):
        '''
        return all the notifications

        :return: dict
        :rtype: dict
        usage::
            >>> zen.get_device_classes("/Network")
            {
                'success': True,
                'data': [{
                    u'action': u'email',
                    u'content': {...},
                    ...
                }]
            }
        '''
        return self.__router_request('TriggersRouter', 'getNotifications', [{}])

    def get_triggers(self):
        '''
        gather all the triggers

        :return: zenoss success dict, where all the triggers are under the data key
        :rtype: dict

        usage::
        >>> zen.get_triggers()
        {u'data': [{
            u'enabled': True,
            u'globalManage': True,
            u'globalRead': True,
            u'globalWrite': True,
            u'name': u'RuleName',
            u'rule': {
                u'api_version': 1,
                u'source': u'(dev.production_state == 1000) and (evt.severity >= 4)',
                u'type': 1},
            u'subscriptions': [
                {
                    u'delay_seconds': 0,
                    u'repeat_seconds': 0,
                    u'send_initial_occurrence': True,
                    u'subscriber_uuid': u'...',
                    u'trigger_uuid': u'...',
                    u'uuid': u'...'},
                {
                    u'delay_seconds': 1,
                    u'repeat_seconds': 60,
                    u'send_initial_occurrence': True,
                    u'subscriber_uuid': u'...',
                    u'trigger_uuid': u'...',
                    u'uuid': u'...'}
            ],
            u'userManage': True,
            u'userRead': True,
            u'userWrite': True,
            u'users': [],
            u'uuid': u'...'}],
        u'success': True}
        '''
        return self.__router_request('TriggersRouter', 'getTriggers', [{}])

    def get_zproperties(self, uid):
        '''
        take any uid to a zenoss object and return the zproperties for the object

        :param uid: Specify the zenoss uid for object to inspect
        :type uid: string
        :return: zenoss response dict where data key holds all the properties
        :rtype: dict
        usage::
            >>> zen.get_zproperties("/zport/dmd/Devices/Network")
            {u'data': [ {
                u'category': u'Modeler Controls',
                u'description': u'Allows you to set the timeout time of the collector client in seconds',
                u'id': u'zCollectorClientTimeout',
                u'islocal': 0,
                u'label': u'Collector Client Timeout (seconds)',
                u'options': [],
                u'path': u'/',
                u'type': u'int',
                u'value': 180,
                u'valueAsString': 180},
                ...
                ]
            u'success': True,
            u'totalCount': 81
        }
        '''
        return self.__router_request('PropertiesRouter', 'getZenProperties',
                                     uri="%s%s/properties_router" % (self.__host, uid),
                                     data=[dict(uid=uid)])

    def remove_device_class(self, name, path=""):
        '''
        remove a given device class from zenoss

        :param name: name of device class to be removed
        :type name: string
        :param path: path to device class endpoint
        :type path: string
        :return: dict showing the status of the command
        :rtype: dict
        usage::
            >>> zen.remove_device_class("Switch", path="/Network")
            {u'msg': u"Deleted node '/zport/dmd/Devices/HTTP/Test'", u'success': True}
        '''
        base_org = "/zport/dmd/Devices%s" % path
        data = dict(uid="%s/%s" % (base_org, name))
        return self.__router_request('DeviceRouter', 'deleteNode', [data])

    def remove_event_class(self, name, path=""):
        '''
        remove an event class

        :param name: the endpoint name of the event class to be removed
        :type name: string
        :param path: path to where the event class is located
        :type path: string
        :return: zenoss success dict
        :rtype: dict

        usage::
            >>> zen.remove_event_class("Testing", path="/Net")
                {u'success': True}
        '''
        base_org = "/zport/dmd/Events%s" % path
        data = dict(uid="%s/%s" % (base_org, name))
        return self.__router_request('EventClassesRouter', 'deleteEventClass', [data])

    def remove_group(self, group, path=""):
        '''
        Deletes a Group organizer
        :param group: name of group to be deleted
        :type group: string
        :param path: path to organizer holding group
        :type path: string
        :return: zenoss success dict
        :rtype: dict

        usage::
            >>> zen.remove_group("MyGroup")
            {u'msg': u"Deleted node '/zport/dmd/Groups/MyGroup'", u'success': True}
        '''
        base_org = "/zport/dmd/Groups%s" % path
        log.info('Removing Group %s', group)
        data = dict(uid="%s/%s" % (base_org, group))
        return self.__router_request('DeviceRouter', 'deleteNode', [data])

    def remove_locations(self, location, path=""):
        '''
        Deletes a Location organizer

        :param location: name of the location to be remove
        :type location: string
        :param path: path to the location organizer
        :type path: string
        :return: zenoss success dict
        :rtype: dict
        usage::
            >>> zen.remove_locations("Springfield")
            {u'msg': u"Deleted node '/zport/dmd/Locations/Springfield'", u'success': True}
        '''
        base_org = "/zport/dmd/Locations%s" % path
        log.info('Removing Location %s', location)
        data = dict(uid="%s/%s" % (base_org, location))
        return self.__router_request('DeviceRouter', 'deleteNode', [data])

    def remove_trigger(self, name):
        '''
        delete a trigger

        :param name: name of trigger to be removed
        :type name: string
        usage::
            >>> zen.remove_trigger('TEST')
            {u'data': None,
            u'msg': u'Trigger removed successfully. 0 notifications were updated.',
            u'success': True}
        '''
        all_triggers = dict()
        for _ in self.get_triggers()['data']:
            all_triggers[_['name']] = _
        if name not in all_triggers:
            raise ZenossException("Unable to find trigger %s" % (name))
        uuid = all_triggers[name]['uuid']
        return self.__router_request('TriggersRouter', 'removeTrigger', [dict(uuid=uuid)])

    def set_ec_instance_details(self, name, transform, path="", is_uid=False):
        '''
        modify an event class details

        :param name: name of the event class
        :type name: string
        :param transform: transform code
        :type transform: string
        :param path: path to even class
        :type path: string
        :param is_uid: is the name provided a uid, saves on look ups
        :type is_uid: boolean
        :return: zenoss success dict
        :rtype: dict

        usage::

        '''
        if is_uid:
            data = dict(uid=name, transform=transform)
        else:
            base_org = "/zport/dmd/Events%s" % path
            data = dict(uid="%s/instances/%s" % (base_org, name))
        return self.__router_request('EventClassesRouter', 'setTransform', [data])

    def update_notifiication_sub(self, name, subscriptions, by_name=False):
        '''
        update the notification subscription

        :param name: name of the notification
        :type name: string
        :param subscription: list of uids for this notification to subscribe to
        :type subscription: list
        :param by_name: flag to send a list of trigger names, not uuids of triggers
        :type by_name: boolean
        usage::
            >>> zen.update_notification_sub('Test', ['f1f9eb4b-090b-4021-8e26-e535b29077c5'])
            {u'data': None,
             u'msg': u'Notification updated successfully.',
             u'success': True}
        '''
        all_notifications = dict()
        for _ in self.get_notifications()['data']:
            all_notifications[_['name']] = _
        if name not in all_notifications:
            raise ZenossException("Unable to find notification %s" % name)
        if by_name:
            all_triggers = dict()
            for _ in self.get_triggers()['data']:
                all_triggers[_['name']] = _
            tmp = list()
            for _ in subscriptions:
                if _ in all_triggers:
                    tmp.append(all_triggers[_]['uuid'])
                else:
                    raise ZenossException("Unable to map trigger %s to notification %s" % (
                        _,
                        name
                    ))
            subscriptions = tmp
        else:
            diff = set(subscriptions).difference(
                set([_['uuid'] for _ in self.get_triggers()['data']]))
            if diff:
                raise ZenossException("Passed trigger subscription uuid that doesn't exist %s" % diff)
        data = all_notifications[name]
        data['subscriptions'] = subscriptions
        return self.__router_request('TriggersRouter', 'updateNotification', [data])

    def update_trigger_rules(self, name, rule=None, users=None, enabled=True,
                             global_manage=False, global_read=False, global_write=False):
        '''
        modify an existing trigger

        NOTE: is the request isn't properly formatted zenoss might just accept it, and return
        success.

        :param name: name of the trigger
        :type name: string
        :param rule: event rule string
        :type rule: string
        :param users: list of dicts for user setting definitions
        :type rule: list
        :param enabled: is the trigger enabled
        :type enabled: boolean
        :param global_manage: is the trigger manageable by all, can it be deleted
        :type global_manage: boolean
        :param global_read: is the trigger readable by all, can it be seen
        :type gloabl_read: boolean
        :param global_write: is the trigger writable by all, can it be updated
        :type global_write: boolean
        :return: zenoss success dict
        :rtype: dict

        usage::
            >>> zen.update_trigger_rules("dc1_bgp", enabled=False)
            {u'data': u'', u'msg': u'Trigger updated successfully.', u'success': True}
        '''
        all_triggers = dict()
        for _ in self.get_triggers()['data']:
            all_triggers[_['name']] = _
        if name not in all_triggers:
            raise ZenossException("Unable to find trigger %s" % (name))
        if not rule:
            rule = all_triggers[name]['rule']['source']
        uuid = all_triggers[name]['uuid']
        data = dict(
            enabled=enabled,
            globalManage=global_manage,
            globalRead=global_read,
            globalWrite=global_write,
            name=name,
            uuid=uuid,
            rule=dict(source=rule)
        )
        if users:
            data['users'] = users
        return self.__router_request('TriggersRouter', 'updateTrigger', [data])
