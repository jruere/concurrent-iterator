from __future__ import annotations

import abc
import logging
import time
from collections.abc import Iterable, Iterator
from contextlib import closing
from typing import Any, TypeVar
from unittest import mock

from concurrent_iterator import IConsumer, IProducer

T = TypeVar("T")

logging.basicConfig(level=logging.CRITICAL)


class ProducerTestMixin(metaclass=abc.ABCMeta):
    # Provide TestCase assertions for mypy (mixin is always used with unittest.TestCase)
    assertEqual: Any
    assertAlmostEqual: Any
    assertRaises: Any
    assertTrue: Any
    assertFalse: Any
    assertLess: Any

    @abc.abstractmethod
    def _create_producer(self, iterable: Iterable[T]) -> IProducer[T]:
        raise NotImplementedError

    def test_when_a_generator_is_spawned_then_it_generates_the_same_values(
        self,
    ) -> None:
        values = [1, 2, 3]

        subject = self._create_producer(iter(values))

        results = list(subject)

        self.assertEqual(values, results)

    def test_when_generating_element_takes_time_then_it_should_be_faster_than_sequential(
        self,
    ) -> None:
        def gen(count: int, delay: float) -> Iterator[int]:
            for i in range(count):
                time.sleep(delay)
                yield i

        count = 3
        delay = 0.1

        subject = self._create_producer(iter(gen(count, delay)))

        time.sleep(0.2 + count * delay)  # Give background thread time to consume.

        t0 = time.time()
        results = list(subject)
        tf = time.time() - t0

        self.assertEqual(list(range(count)), results)
        self.assertAlmostEqual(0, tf, 1)

    def test_when_a_producer_raises_an_exception_then_it_is_sent_to_the_main_thread_and_the_producer_terminates(
        self,
    ) -> None:
        def throwing_generator() -> Iterator[int]:
            yield 1
            raise AssertionError("Test exception")
            yield 2  # type: ignore[unreachable]

        iterable = throwing_generator()
        subject = self._create_producer(iterable)

        self.assertEqual(1, next(subject))
        self.assertRaises(AssertionError, next, subject)
        self.assertRaises(StopIteration, next, subject)
        self.assertRaises(StopIteration, next, subject)


class ConsumerTestMixin(metaclass=abc.ABCMeta):
    assertRaises: Any
    assertEqual: Any

    @abc.abstractmethod
    def _create_consumer(self, coroutine: Any) -> IConsumer[Any]:
        raise NotImplementedError

    def test_when_a_value_is_sent_then_it_is_forwarded_to_the_coroutine(self) -> None:
        coroutine = mock.MagicMock()

        with closing(self._create_consumer(coroutine)) as subject:
            subject.send("a value")

        coroutine.send.assert_called_once_with("a value")

    def test_when_closed_then_sending_should_not_work(self) -> None:
        coroutine = mock.MagicMock()

        subject = self._create_consumer(coroutine)

        subject.close()

        self.assertRaises(ValueError, subject.send, 0)
        coroutine.assert_has_calls([])

    def test_when_closed_then_closing_should_not_work(self) -> None:
        coroutine = mock.MagicMock()

        subject = self._create_consumer(coroutine)

        subject.close()

        self.assertRaises(ValueError, subject.close)
        coroutine.assert_has_calls([])

    def test_when_closed_then_it_should_close_the_passed_coroutine(self) -> None:
        coroutine = mock.MagicMock()

        subject = self._create_consumer(coroutine)
        subject.close()

        coroutine.close.assert_called_once_with()
