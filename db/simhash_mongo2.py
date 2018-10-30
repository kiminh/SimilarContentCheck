#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : Joshua
@Time    : 2018/10/19 16:30
@File    : simhash_mongo.py
@Desc    : simhash storage of fingerprint and simhash inverted index with mongodb
"""

import datetime
import time

from mongoengine import register_connection
from mongoengine import connect
from setting import simhash_mongodb_config
from mongoengine import Document, IntField
from mongoengine import StringField, DateTimeField

register_connection(**simhash_mongodb_config)

# _retry = 0
# _status = False
# while not _status and _retry <= 3:
#     try:
#         connect('simhash', host='mongodb://localhost:27017/simhash_invert_index')
#         _status = True
#     except:
#         print("连接失败，正在重试")
#         _status = False
#         _retry += 1
#         time.sleep(2)
#         if _retry == 4:
#             raise Exception("Mongodb连接失败，请检查")

class SimhashInvertedIndex(Document):
    """
    simhash inverted index
    """
    obj_id = StringField()
    # hash_value = StringField()  # OverflowError: MongoDB can only handle up to 8-byte ints
    key = StringField()
    # simhash_caches_index = ListField(StringField())  # hash_value,obj_id
    simhash_value_obj_id = StringField()  # hash_value,obj_id
    # hash_type = StringField()
    add_time = DateTimeField(default=datetime.datetime.now())
    update_time = DateTimeField(default=datetime.datetime.now())
    last_days = IntField(default=0)
    meta = {
        'db_alias': 'simhash',
        'strict': False,
        # 'index_background': True ,
        "collection": "simhash_invert_index",
        "indexes": [
            "key",
            "simhash_value_obj_id",
            "-add_time",
            "-update_time",
            "last_days",
            "obj_id",
            # "hash_value",
            # "hash_type",
            {
                    "fields": ["key", 'simhash_value_obj_id'],
                    "unique":True,
            },
        ]
    }

    def __str__(self):

        return 'obj_id:{}'.format(self.obj_id)


def get_all_simhash(SimHashCache):
    # print('db:{}\ncount: {} records'.format(SimHashCache._meta['db_alias'], len(records)))
    return list(SimHashCache.objects.all())

def get_simhash_count(SimHashCache):

    return len(list(SimHashCache.objects.all()))

if __name__ == '__main__':
    all = get_all_simhash(SimhashInvertedIndex)
    print(all)
    objs = list()
    for i in all:
        objs.append((i['obj_id']))
    print(objs)
    SimhashInvertedIndex.objects(obj_id='test1').delete()