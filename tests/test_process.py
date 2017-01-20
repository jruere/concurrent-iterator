# vim: set fileencoding=utf-8
from contextlib import closing
import logging
import multiprocessing.managers
import unittest

from concurrent_iterator.process import Producer, Consumer
from tests import ProducerTestMixin


logging.basicConfig(level=logging.DEBUG)


class ProcessProducerTestChunk1(unittest.TestCase, ProducerTestMixin):

    def _create_producer(self, iterable):
        return Producer(iterable, chunksize=1)


class ProcessProducerTestChunk2(unittest.TestCase, ProducerTestMixin):

    def _create_producer(self, iterable):
        return Producer(iterable, chunksize=2)


class ProcessConsumerTest(unittest.TestCase):

    class Coroutine(object):

        def __init__(self):
            self.values = []
            self.closed = False

        def send(self, value):
            self.values.append(value)

        def get_values(self):
            return list(self.values)

        def close(self):
            self.closed = True

        def get_closed(self):
            return self.closed

    def _create_consumer(self, coroutine):
        return Consumer(coroutine)

    def setUp(self):
        manager = multiprocessing.managers.BaseManager()
        manager.register('Coroutine', ProcessConsumerTest.Coroutine)
        manager.start()
        self.coroutine = manager.Coroutine()

    def test_when_a_value_is_sent_then_it_is_forwarded_to_the_coroutine(self):
        with closing(self._create_consumer(self.coroutine)) as subject:
            subject.send("a value")

        self.assertEqual(["a value"], self.coroutine.get_values())

    def test_when_closed_then_sending_should_not_work(self):
        subject = self._create_consumer(self.coroutine)

        subject.close()

        self.assertRaises(ValueError, subject.send, 0)
        self.assertEqual([], self.coroutine.get_values())

    def test_when_closed_then_closing_should_not_work(self):
        subject = self._create_consumer(self.coroutine)

        subject.close()

        self.assertRaises(ValueError, subject.close)
        self.assertEqual([], self.coroutine.get_values())

    def test_when_closed_then_it_should_close_the_passed_coroutine(self):
        subject = self._create_consumer(self.coroutine)
        subject.close()

        self.assertTrue(self.coroutine.get_closed())
