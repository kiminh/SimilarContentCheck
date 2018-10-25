#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : Joshua
@Time    : 2018/10/12 17:16
@File    : similarity_check.py
@Desc    : 
"""

import threading
import time
from queue import Queue

from db.simhash_mongo import SimHashCache, SimhashInvertedIndex, get_all_simhash
from db.simhash_redis import SimhashRedis
from extract_features.extract_features_participle import Participle
from extract_features.extract_features_tfidf import get_keywords_tfidf
from fingerprints_calculation.simhash import Simhash
from fingerprints_storage.simhash_index_redis import SimhashIndexWithRedis


class SimilarityCheck(object):

    def __init__(self, hashbits=64, k=3):
        self.hashbits = hashbits
        self.k = k

        self.redis = SimhashRedis()
        self.simhashcache = SimHashCache
        self.simhash_inverted_index = SimhashInvertedIndex

        self.objs = [(obj[0], obj[1]) for obj in self.get_simhash_from_mongodb(self.simhashcache)]
        self.invert_index = [(obj[0], obj[1]) for obj in self.get_inverted_index_from_mongodb(self.simhash_inverted_index)]

        self.db = SimhashIndexWithRedis(self.simhashcache, self.simhash_inverted_index, self.redis)

        if self.objs and self.invert_index:
            s4 = time.clock()
            for ii in self.invert_index:
                self.redis.add(ii[0], ii[1])
            s5 = time.clock()
            print("初始化数据库**********{}s".format(s5-s4))

    def _extract_features(self, text, func='participle'):

        if func == 'participle':
            keywords = Participle().get_text_feature(text)
        elif func == 'tfidf':
            keywords = get_keywords_tfidf(text)
        else:
            raise Exception('Please provide a custom function ')

        return keywords

    def check_similarity(self, text, text_id):

        s1 = time.clock()
        keywords = self._extract_features(text)
        s2 = time.clock()
        print("分词耗时**********{}s".format(s2 - s1))
        simhash = Simhash(keywords)
        s3 = time.clock()
        print("计算指纹耗时**********{}s".format(s3 - s2))
        s6 = time.clock()
        if not self.objs:
            self.redis.flushdb()
            self.db.add(obj_id=text_id, simhash=simhash)
        dups_list = self.db.get_near_dups(simhash)
        s7 = time.clock()
        print("查找耗时**********{}s".format(s7-s6))
        self.db.add(obj_id=text_id, simhash=simhash)
        return dups_list

    def update_db(self, update_frequency=3, keep_days=1):
        print('更新数据库')
        start_time = time.time()
        while True:
            if time.time() - start_time > update_frequency * 10:
                self._check_mongodb(keep_days=keep_days)
                start_time = time.time()

    def _check_mongodb(self, keep_days=30):
        print('正在更新数据库')
        for fingerprint in self.get_simhash_from_mongodb(self.simhashcache):
            if fingerprint[2] >= keep_days:
                self.db.delete(obj_id=fingerprint['obj_id'], simhash=fingerprint['hash_value'])

    @staticmethod
    def get_simhash_from_mongodb(db):

        records = get_all_simhash(db)
        for record in records:
            yield list([record['obj_id'], record['hash_value'], record['last_days']])

    @staticmethod
    def get_inverted_index_from_mongodb(db):
        records = get_all_simhash(db)
        for record in records:
            yield list([record['key'], record['simhash_value_obj_id']])


class TextThread(threading.Thread):

    def __init__(self, task_queue, result_queue, func):
        super(TextThread, self).__init__()
        self.task = task_queue
        self.result = result_queue
        self.check_similarity = func

    def run(self):
        while self.task.qsize() > 0:
            item = self.task.get()
            text, text_id = item
            dups_list = self.check_similarity(text, text_id)
            self.result.put({text_id: dups_list})


def main():
    task_queue = Queue()
    result_queue = Queue()

    simcheck = SimilarityCheck()

    text = "Natural language processing (NLP) is a field of computer science, artificial intelligence and computational linguistics concerned with the interactions between computers and human (natural) languages, and, in particular, concerned with programming computers to fruitfully process large natural language corpora. Challenges in natural language processing frequently involve natural language understanding, natural language generation (frequently from formal, machine-readable logical forms), connecting language and machine perception, managing human-computer dialog systems, or some combination thereof." \
           "The Georgetown experiment in 1954 involved fully automatic translation of more than sixty Russian sentences into English. The authors claimed that within three or five years, machine translation would be a solved problem.[2] However, real progress was much slower, and after the ALPAC report in 1966, which found that ten-year-long research had failed to fulfill the expectations, Little further research in machine translation was conducted until the late 1980s, when the first statistical machine translation systems were developed." \
           "During the 1970s, many programmers began to write conceptual ontologies, which structured real-world information into computer-understandable data. Examples are MARGIE (Schank, 1975), SAM (Cullingford, 1978), PAM (Wilensky, 1978), TaleSpin (Meehan, 1976), QUALM (Lehnert, 1977), Politics (Carbonell, 1979), and Plot Units (Lehnert 1981). During this time, many chatterbots were written including PARRY, Racter, and Jabberwacky。"
    text_id = 'test'

    for i in range(10000):
        id = text_id + str(i)
        salt = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        _text = text + salt
        task = (_text, id)
        task_queue.put(task)
        # time.sleep(2)
    print('已加入任务队列')

    thread_list = []
    thread_1 = threading.Thread(target=simcheck.update_db)
    thread_list.append(thread_1)
    thread_2 = TextThread(task_queue, result_queue, func=simcheck.check_similarity)
    thread_list.append(thread_2)
    for thr in thread_list:
        thr.setDaemon(True)
        thr.start()
    while not result_queue.qsize():
        print(result_queue.get())

    print(task_queue.qsize())
    print(thread_2.isAlive())

    if not thread_2.isAlive() and not task_queue.qsize():
        thread_1._stop()
        thread_1.join()
    else:
        thread_2.join()


if __name__ == '__main__':
    import random
    import string
    # s = SimilarityCheck()
    # # for i in s.get_inverted_index_from_mongodb(s.simhash_inverted_index):
    # #     print(i)
    # text = "Natural language processing (NLP) fully automatic translation of more than sixty Russian sentences into English. The authors claimed that within three or five years, machine translation would be a solved problem.[2] However, real progress was much slower, and after the ALPAC report in 1966, which found that ten-year-long research had failed to fulfill the expectations, Little further research in machine translation was conducted until the late 1980s, when the first statistical machine translation systems were developed." \
    #        "During the 1970s, many programmers began to write conceptual ontologies, which structured real-world information into computer-understandable data. Examples are MARGIE (Schank, 1975), SAM (Cullingford, 1978), PAM (Wilensky, 1978), TaleSpin (Meehan, 1976), QUALM (Lehnert, 1977), Politics (Carbonell, 1979), and Plot Units (Lehnert 1981). During this time, many chatterbots were written including PARRY, Racter, and Jabberwacky。"
    # id = 'testxx'
    # for i in range(1000000):
    #     _text = text + str(i*25)
    #     _id = id + str(i)
    #     dups = s.check_similarity(_text, _id)
    #     print(dups)
    # print(s.redis.status)
    main()