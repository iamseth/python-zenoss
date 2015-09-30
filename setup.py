#!/usr/bin/env python

from setuptools import setup

setup(name='zenoss',

version='0.6.2',
    description='Module to work with the Zenoss JSON API.',
    author="Seth Miller",
    author_email='seth@sethmiller.me',
    url='https://github.com/iamseth/python-zenoss',
    py_modules=['zenoss',],
    keywords = ['zenoss', 'api', 'json', 'rest'],
    test_suite='tests'
)
