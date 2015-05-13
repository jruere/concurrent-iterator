# vim: set fileencoding=utf-8
import logging
import unittest

from concurrent_iterator.thread import Producer, Consumer
from tests import ProducerTestMixin, ConsumerTestMixin


logging.basicConfig(level=logging.WARNING)


class ThreadProducerTest(unittest.TestCase, ProducerTestMixin):

    def _create_producer(self, iterable):
        return Producer(iterable)


class ThreadConsumerTest(unittest.TestCase, ConsumerTestMixin):

    def _create_consumer(self, coroutine):
        return Consumer(coroutine)
