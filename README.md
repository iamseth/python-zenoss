python-zenoss
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

zenoss = Zenoss()
zenoss.connect('http://zenoss:8080/', 'admin', 'password')

for device in zenoss.get_devices()['devices']:
    print(device['name'])
```

