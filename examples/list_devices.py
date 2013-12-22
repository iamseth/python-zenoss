#!/usr/bin/env python

from zenoss import Zenoss

zenoss = Zenoss()
zenoss.connect('http://zenoss:8080/', 'admin', 'password')

for device in zenoss.get_devices()['devices']:
    print(device['name'])

