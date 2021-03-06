#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : Joshua
@Time    : 2018/10/12 15:38
@File    : simhash_index_redis.py
@Desc    : simhash storage with mongodb and redis
"""

import time
import logging

from setting import SAVE_DAYS
from db.simhash_mongo import SimhashInvertedIndex
from fingerprints_calculation.simhash import Simhash
from similarity_calculation.hamming_distance import HammingDistance


class SimhashIndexWithRedis(object):

    def __init__(self, simhashinvertedindex, redis, objs=(), hashbits=64, k=3, logger=None):
        """
        Args:
            redis: an instance of redis
            simhashinvertedindex : an instance of simhashinvertedindex(mongodb)
            objs: a list of (obj_id, origin_text)
                obj_id is a string, simhash is an instance of Simhash
            hashbits: the same with the one for Simhash
            k: the tolerance
            logger:  an instance of Logger
        """
        if logger is None:
            self.log = logging.getLogger("simhash")
        else:
            self.log = logger

        self.k = k
        # TODO: 根据实际情况修改两篇相似文章间的距离(默认距离为小于6，认为两篇文章重复)
        self.distance = 7
        self.hashbits = hashbits
        # self.hash_type = hash_type
        self.redis = redis
        self.simhash_inverted_index = simhashinvertedindex

        if objs:
            count = len(objs)
            self.log.info('Initializing {} data.'.format(count))

            for i, q in enumerate(objs):
                if i % 10000 == 0 or i == count - 1:
                    self.log.info('{}/{}'.format(i + 1, count))
                self.add(*q)

    def add(self, obj_id, simhash):
        return self._insert(obj_id=obj_id, value=simhash)

    def update(self, obj_id):
        if self.simhash_inverted_index.objects(obj_id=obj_id):
            for row in self.simhash_inverted_index.objects(obj_id=obj_id):
                add_time = row.add_time
                update_time = int(time.time())
                last_days = (update_time - add_time) // 3600*24
                if last_days > SAVE_DAYS:
                    row.delete()
                row.save()
        return

    def delete(self, obj_id, simhash):
        """
        Args:
            obj_id: a string
            simhash: an instance of Simhash or str
        """
        if isinstance(simhash, str):
            simhash = Simhash(value=simhash, hashbits=self.hashbits)
        elif isinstance(simhash, Simhash):
            simhash = simhash
        else:
            self.log.warning('simhash not str or an instance of Simhash')
            pass

        # delete simhash in mongodb
        try:
            self.simhash_inverted_index.objects(obj_id=obj_id).delete()
        except:
            self.log.warning('Delete obj_id {} wrong'.format(obj_id))
        # delete simhash in redis
        for key in self.get_keys(simhash):
            v = '{:x},{}'.format(simhash.fingerprint, obj_id)
            self.redis.delete(name=key, value=v)
        return

    def get_near_dups(self, simhash):
        """
        Args:
            simhash: an instance of Simhash
        Returns:
            return a list of obj_id, which is in type of str
        """
        return self._find(simhash, self.distance)

    def get_keys(self, simhash):
        for i, offset in enumerate(self.offsets):
            # m = (i == len(self.offsets) - 1 and 2 ** (self.hashbits - offset) - 1 or 2 ** (self.offsets[i + 1] - offset) - 1)
            if i == len(self.offsets) - 1:
                m = 2 ** (self.hashbits - offset) - 1
            else:
                m = 2 ** (self.offsets[i + 1] - offset) - 1
            c = simhash.fingerprint >> offset & m
            yield '{:x}:{:x}'.format(c, i)

    def _insert(self, obj_id=None, value=None):
        """Insert hash value into mongodb and redis
            data can  be text,{obj_id,text},  {obj_id,simhash}
        #TODO: The most time-consuming place to store and write databases
        """
        assert value != None
        if isinstance(value, str):
            simhash = Simhash(value=value, hashbits=self.hashbits)
        elif isinstance(value, Simhash):
            simhash = value
        else:
            raise Exception('Value not text or simhash')
        assert simhash.hashbits == self.hashbits

        # Cache raw text information
        if obj_id and simhash:

            # Store or update the cache to mongodb,cache invert index into mongodb and redis
            v = '{:x},{}'.format(simhash.fingerprint, obj_id)  # Convert to hexadecimal for compressed storage, which saves space and converts back when querying
            for key in self.get_keys(simhash):
                try:
                    invert_index = self.simhash_inverted_index(key=key, simhash_value_obj_id=v)
                    add_time = int(time.time())
                    invert_index.add_time = add_time
                    invert_index.obj_id = obj_id
                    # invert_index.last_days = (update_time - add_time) // (3600*24)
                    # invert_index.hash_value = '{:x}'.format(simhash.fingerprint)
                    invert_index.save()

                    self.redis.add(name=key, timenode=add_time, value=v)
                except Exception as e:
                    # print('%s,%s,%s' % (e, key, v))
                    self.log.warning('DB has same value{}'.format(e))
                    pass


    def _find(self, value, distance=4):
        assert value != None

        if isinstance(value, str):
            simhash = Simhash(value=value, hashbits=self.hashbits)
        elif isinstance(value, Simhash):
            simhash = value
        else:
            self.log.warning('value not text or simhash')
            raise Exception('value not text or simhash')

        assert simhash.hashbits == self.hashbits
        ans = set()
        for key in self.get_keys(simhash):
            try:
                simhash_list = self.redis.get_values(name=key)
            except:
                self.log.warning('Wrong with getting values from redis')
            else:
                if len(simhash_list) > 1000:
                    self.log.warning('Big bucket found. key:{}, len:{}'.format(key, len(simhash_list)))

                for simhash_cache in simhash_list:
                    if isinstance(simhash_cache, bytes):
                        simhash_cache = simhash_cache.decode()

                    try:
                        sim2, obj_id = simhash_cache.split(',', 1)
                        _sim2 = Simhash(int(sim2, 16), self.hashbits)

                        _sim1 = HammingDistance(simhash)
                        d = _sim1.distance(_sim2)

                        if d < distance:
                            ans.add(obj_id)
                    except Exception as e:
                        self.log.warning('Not exists {}'.format(e))
        return list(ans)

    def find_similiar(self, obj_id):
        """Find similar objects by obj_id"""
        simhash_caches = self.simhash_inverted_index.objects.filter(obj_id__contains=obj_id)
        return simhash_caches

    @property
    def offsets(self):
        return [self.hashbits // (self.k + 1) * i for i in range(self.k + 1)]

    @property
    def bucket_size(self):
        return self.redis.status

if __name__ == '__main__':
    from db.simhash_redis import SimhashRedis
    sim = Simhash(int('ab2f0faeeabf5e4a', 16))
    s = SimhashIndexWithRedis(SimhashInvertedIndex, SimhashRedis())
    print(s.get_near_dups(sim))
    # import random
    # import string
    # for i in range(100):
    #     obj_id = 'test'+ str(i)
    #     salt = ''.join(random.sample(string.ascii_letters + string.digits, 60))
    #     value = 'weoigjnalksdmgl;kansd;kgnqw;smdfkasndg;olqwokmdfl,ndg;qw' + salt
    #     simhash = Simhash(value)
    #     test = s.add(obj_id, value)
    #     print(test)
    #     # s.delete('test3', simhash)
    #     print(s.bucket_size)
    # a = s.redis.get('a903:2')
    # print(a)
    # s = SimhashInvertedIndex
    # for i in s.objects(obj_id='1491824535189884', key='4d9d:3'):
    #     add_time = i.add_time
    #     print(add_time)
    #     update_time = datetime.datetime.now()
    #     i.update_time = update_time
    #     i.last_days = (update_time - add_time).days
    #     if i.last_days == 0:
    #         i.delete()
    #     i.save()
