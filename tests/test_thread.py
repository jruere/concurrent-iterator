# vim: set fileencoding=utf-8

from __future__ import division

import itertools
import logging
import unittest

from concurrent_iterator.thread import MultiProducer, Producer, Consumer
from tests import ProducerTestMixin, ConsumerTestMixin
import time


logging.basicConfig(level=logging.WARNING)

class ThreadMultiProducerTest(unittest.TestCase):

    def test_when_multiple_iterables_have_data_then_it_should_consume_from_all_of_them(self):
        subject = MultiProducer([range(3), range(5, 10)], maxsize=1)
        results = sorted(subject)

        expected = list(itertools.chain(range(3), range(5, 10)))
        self.assertEqual(expected, results)


class ThreadProducerTest(unittest.TestCase, ProducerTestMixin):

    def _create_producer(self, iterable):
        return Producer(iterable)


class ThreadConsumerTest(unittest.TestCase, ConsumerTestMixin):

    def _create_consumer(self, coroutine):
        return Consumer(coroutine)

def rotate(iterable, rank):
    return iterable[-rank:] + iterable[:-rank]

class ThreadRingQueueTest(unittest.TestCase):

    def test_ring_policy_work_correctly(self):
        def gen(count):
            for i in range(count):
                yield i

        count = 5
        maxsize = 2

        producer = Producer(iter(gen(count)), maxsize=maxsize, policy='ring')
        result = list(producer)
        expected_result = rotate(list(gen(count)), int(count / maxsize))[:maxsize]

        self.assertItemsEqual(result, result, expected_result)

    def test_cant_create_policy_with_unknown_policy(self):
        Producer(iter([1,2,3]), policy='linear')
        Producer(iter([1,2,3]), policy='ring')

        with self.assertRaises(ValueError):
            Producer(iter([1,2,3]), policy='mypolicy')

