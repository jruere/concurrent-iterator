# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals

import abc
from contextlib import closing
import time

import mock


class ProducerTestMixin(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def _create_producer(self, iterable):
        pass

    def test_when_a_generator_is_spawned_then_it_generates_the_same_values(self):
        values = [1, 2, 3]

        subject = self._create_producer(iter(values))

        results = list(subject)

        self.assertEqual(values, results)

    def test_when_generating_element_takes_time_then_it_should_be_faster_than_sequential(self):
        def gen(count, delay):
            for i in range(count):
                time.sleep(delay)
                yield i

        count = 3
        delay = 0.1

        subject = self._create_producer(iter(gen(count, delay)))

        time.sleep(count * delay)  # Give background thread time to consume.

        t0 = time.time()
        results = list(subject)
        tf = time.time() - t0

        self.assertEqual(list(range(count)), results)
        self.assertAlmostEqual(0, tf, 1)


class ConsumerTestMixin(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def _create_consumer(self, coroutine):
        pass

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

    def test_when_closed_then_it_should_close_the_passed_coroutine(self):
        coroutine = mock.MagicMock()

        subject = self._create_consumer(coroutine)
        subject.close()

        coroutine.close.assert_called_once_with()
