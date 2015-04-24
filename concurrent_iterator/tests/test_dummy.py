# vim: set fileencoding=utf-8

from contextlib import closing
import logging
import unittest

from concurrent_iterator.dummy import Producer, Consumer
from concurrent_iterator.tests import AbstractProducerTest

import mock


logging.basicConfig(level=logging.WARNING)


class DummyProducerTest(unittest.TestCase, AbstractProducerTest):

    def _create_producer(self, iterable):
        return Producer(iterable)

    def test_when_generating_element_takes_time_then_it_should_be_faster_than_sequential(self):
        pass  # Disabled since the dummy implementation is not concurrent.


class DummyConsumerTest(unittest.TestCase):

    def _create_consumer(self, coroutine):
        return Consumer(coroutine)

    def test_when_a_value_is_sent_then_it_is_forwarded_to_the_coroutine(self):
        coroutine = mock.MagicMock()

        with closing(self._create_consumer(coroutine)) as subject:
            subject.send("a value")

        coroutine.send.assert_called_once_with("a value")

    def test_when_closed_then_sending_should_not_work(self):
        coroutine = mock.MagicMock()

        subject = self._create_consumer(coroutine)

        subject.close()

        self.assertRaises(ValueError, subject.send, 0)
        coroutine.assert_has_calls([])

    def test_when_closed_then_closing_should_not_work(self):
        coroutine = mock.MagicMock()

        subject = self._create_consumer(coroutine)

        subject.close()

        self.assertRaises(ValueError, subject.close)
        coroutine.assert_has_calls([])
