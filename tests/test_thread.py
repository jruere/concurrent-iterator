# vim: set fileencoding=utf-8
import logging
import unittest

from concurrent_iterator.thread import Producer
from tests import ProducerTestMixin


logging.basicConfig(level=logging.WARNING)


class ThreadProducerTest(unittest.TestCase, ProducerTestMixin):

    def _create_producer(self, iterable):
        return Producer(iterable)
