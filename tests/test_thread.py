from __future__ import annotations

import itertools
import logging
import time
import unittest
from collections.abc import Iterable
from typing import Any, TypeVar

from concurrent_iterator.thread import Consumer, MultiProducer, Producer
from tests import ConsumerTestMixin, ProducerTestMixin

T = TypeVar("T")

logging.basicConfig(level=logging.WARNING)


class ThreadProducerTest(unittest.TestCase, ProducerTestMixin):
    def _create_producer(self, iterable: Iterable[T]) -> Producer[T]:
        return Producer(iterable)


class ThreadProducerValidationTest(unittest.TestCase):
    def test_when_maxsize_invalid_then_assertion_error(self) -> None:
        iterable = range(3)

        with self.assertRaises(AssertionError):
            Producer(iterable, maxsize=0)

        with self.assertRaises(AssertionError):
            Producer(iterable, maxsize=-5)


class ThreadConsumerTest(unittest.TestCase, ConsumerTestMixin):
    def _create_consumer(self, coroutine: Any) -> Consumer[Any]:
        return Consumer(coroutine)


class ThreadConsumerCloseTest(unittest.TestCase):
    def test_when_queue_full_then_close_returns_quickly(self) -> None:
        # Coroutine that sleeps to keep queue full
        class Slow:
            def __init__(self) -> None:
                self.values: list[Any] = []

            def send(self, value: Any) -> None:
                time.sleep(1.0)
                self.values.append(value)

            def close(self) -> None:
                pass

        subject: Consumer[Any] = Consumer(Slow(), maxsize=1, close_timeout_secs=0.5)

        subject.send("first")
        # Give thread time to take first value and sleep
        time.sleep(0.05)
        # Queue now has capacity 1 but thread is busy; next send will fill queue
        subject.send("second")
        # Now queue is full (second pending) and thread still sleeping on first

        t0 = time.time()

        subject.close()

        elapsed = time.time() - t0

        # With blocking put, close would need ~2s (first sleep + second sleep).
        # With draining, close only waits for current item (~1s).
        self.assertLess(elapsed, 1.5, "close() should not hang even when queue full")
        self.assertTrue(subject.closed)


class ThreadConsumerValidationTest(unittest.TestCase):
    def test_when_maxsize_invalid_then_assertion_error(self) -> None:
        class Dummy:
            def send(self, _: Any) -> None:
                pass

            def close(self) -> None:
                pass

        coro = Dummy()

        with self.assertRaises(AssertionError):
            Consumer(coro, maxsize=0)

        with self.assertRaises(AssertionError):
            Consumer(coro, maxsize=-5)

        with self.assertRaises(AssertionError):
            Consumer(coro, maxsize=1, close_timeout_secs=0)

        with self.assertRaises(AssertionError):
            Consumer(coro, maxsize=1, close_timeout_secs=-1)


class ThreadMultiProducerTest(unittest.TestCase):
    def test_when_multiple_iterables_have_data_then_it_should_consume_from_all_of_them(
        self,
    ) -> None:
        subject = MultiProducer([range(3), range(5, 10)], maxsize=1)

        results = sorted(subject)

        expected = list(itertools.chain(range(3), range(5, 10)))

        self.assertEqual(expected, results)

    def test_when_no_iterables_then_immediately_closed(self) -> None:
        subject: MultiProducer[int] = MultiProducer([], maxsize=1)

        self.assertTrue(subject.closed)
        self.assertRaises(StopIteration, next, subject)

        subject.close()

        self.assertTrue(subject.closed)

    def test_when_no_iterables_then_close_is_idempotent(self) -> None:
        subject: MultiProducer[int] = MultiProducer([], maxsize=1)

        subject.close()
        subject.close()

        self.assertTrue(subject.closed)
        self.assertRaises(StopIteration, next, subject)
