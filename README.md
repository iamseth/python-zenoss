# This repo is EOL

I'm no longer maintaining this repository. I'm happy that people have found value in this small library but I haven't used Zenoss in 6 years and cannot maintain this. I suggest using [Prometheus](https://prometheus.io/) for your monitoring needs. Please fork this repository for bug fixes and enhancements.

python-zenoss ![Build Status](https://travis-ci.org/iamseth/python-zenoss.png)
=============

Python module to work with the Zenoss JSON API


Installation
=============

### PyPi
```bash
pip install zenoss
```

### Manually
```bash
python setup.py test
python setup.py build
sudo python setup.py install
```


Usage
=============

### List all devices in Zenoss
```python
from zenoss import Zenoss

zenoss = Zenoss('http://zenoss:8080/', 'admin', 'password')

for device in zenoss.get_devices()['devices']:
    print(device['name'])
```

