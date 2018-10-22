#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : Joshua
@Time    : 2018/10/18 18:50
@File    : __init__.py.py
@Desc    : 
"""

import os
from os.path import dirname

# MongoDB
mongodb_config = {
    'name': 'news',
    'username': '',
    'host': '127.0.0.1',
    'password': '',
    'port': 27017,
    'alias': 'default',
}
simhash_mongodb_config = {
    'name': 'simhash',
    'username': '',
    'host': '127.0.0.1',
    'password': '',
    'port': 27017,
    'alias': 'simhash',
}
# Reids
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
REDIS_URL = None

PROJECT_ROOT = dirname(dirname(dirname(os.path.abspath(__file__)))).replace('\\', '/')
LOG_PATH = PROJECT_ROOT + '/logs/'
if not os.path.exists(LOG_PATH):
    os.mkdir(LOG_PATH)
PROJECT_LOG_FILE = LOG_PATH + 'simhash.log'

if __name__ == '__main__':
    print(PROJECT_ROOT)