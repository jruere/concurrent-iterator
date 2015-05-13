# vim: set fileencoding=utf-8

import logging
import unittest

from concurrent_iterator.dummy import Producer, Consumer
from tests import ProducerTestMixin, ConsumerTestMixin


logging.basicConfig(level=logging.WARNING)


class DummyProducerTest(unittest.TestCase, ProducerTestMixin):

    def _create_producer(self, iterable):
        return Producer(iterable)

    def test_when_generating_element_takes_time_then_it_should_be_faster_than_sequential(self):
        pass  # Disabled since the dummy implementation is not concurrent.


class DummyConsumerTest(unittest.TestCase, ConsumerTestMixin):

    def _create_consumer(self, coroutine):
        return Consumer(coroutine)
