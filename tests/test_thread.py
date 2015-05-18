# vim: set fileencoding=utf-8
import itertools
import logging
import unittest

from concurrent_iterator.thread import MultiProducer, Producer, Consumer
from tests import ProducerTestMixin, ConsumerTestMixin


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
