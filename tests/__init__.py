from __future__ import annotations

import abc
import itertools
import logging
import time
from collections.abc import Iterable, Iterator
from contextlib import closing, suppress
from typing import Any, TypeVar
from unittest import mock

from concurrent_iterator import ConsumerCoroutine, IConsumer, IProducer, WillNotConsume

T = TypeVar("T")

logging.basicConfig(level=logging.CRITICAL)


class ThrowingCoroutine:
    """Minimal failing coroutine: raises on `send`.

    Module-level so instances pickle (usable with `spawn`/`forkserver` children).
    """

    def send(self, value: Any) -> None:
        raise RuntimeError(f"boom {value}")

    def close(self) -> None:
        pass


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

    def test_when_closed_early_then_next_raises_stopiteration(self) -> None:
        subject = self._create_producer(itertools.count())

        self.assertEqual(0, next(subject))

        subject.close()

        self.assertTrue(subject.closed)
        self.assertRaises(StopIteration, next, subject)

    def test_when_closed_early_then_close_returns_quickly(self) -> None:
        subject = self._create_producer(itertools.count())

        self.assertEqual(0, next(subject))
        self.assertEqual(1, next(subject))

        t0 = time.time()

        subject.close()

        elapsed = time.time() - t0

        self.assertLess(elapsed, 1.0, "close() should not hang")
        self.assertTrue(subject.closed)

    def test_when_used_as_context_manager_then_closed_on_exit(self) -> None:
        with self._create_producer(itertools.count()) as subject:
            self.assertEqual(0, next(subject))

            self.assertFalse(subject.closed)

        self.assertTrue(subject.closed)
        self.assertRaises(StopIteration, next, subject)

    def test_when_close_called_twice_then_idempotent(self) -> None:
        subject = self._create_producer(range(10))

        subject.close()
        subject.close()

        self.assertTrue(subject.closed)
        self.assertRaises(StopIteration, next, subject)

    def test_when_loop_breaks_early_then_context_manager_prevents_hang(self) -> None:
        with self._create_producer(itertools.count()) as subject:
            for i, _v in enumerate(subject):
                if i == 2:
                    break

            self.assertFalse(subject.closed)

        self.assertTrue(subject.closed)

        with self._create_producer(range(3)) as p2:
            results = list(p2)

        self.assertEqual([0, 1, 2], results)

    def test_when_exhausted_then_close_is_idempotent(self) -> None:
        subject = self._create_producer(range(3))

        results = list(subject)

        subject.close()
        subject.close()

        self.assertEqual([0, 1, 2], results)
        self.assertTrue(subject.closed)

    def test_when_exhausted_then_closed_becomes_true(self) -> None:
        subject = self._create_producer(range(3))

        results = list(subject)

        self.assertEqual([0, 1, 2], results)
        self.assertTrue(subject.closed)
        self.assertRaises(StopIteration, next, subject)


class ConsumerTestMixin(metaclass=abc.ABCMeta):
    assertRaises: Any
    assertEqual: Any
    assertTrue: Any
    assertFalse: Any
    assertIn: Any
    fail: Any

    @abc.abstractmethod
    def _create_consumer(self, coroutine: ConsumerCoroutine[Any]) -> IConsumer[Any]:
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
        coroutine.send.assert_not_called()

    def test_when_closed_then_it_should_close_the_passed_coroutine(self) -> None:
        coroutine = mock.MagicMock()

        subject = self._create_consumer(coroutine)
        subject.close()

        coroutine.close.assert_called_once_with()

    def test_when_used_as_context_manager_then_closed_on_exit(self) -> None:
        coroutine = mock.MagicMock()

        with self._create_consumer(coroutine) as subject:
            subject.send("a")

            self.assertFalse(subject.closed)

        self.assertTrue(subject.closed)
        self.assertRaises(ValueError, subject.send, "b")

    def test_when_close_called_twice_then_idempotent(self) -> None:
        coroutine = mock.MagicMock()

        subject = self._create_consumer(coroutine)

        subject.close()
        subject.close()

        self.assertTrue(subject.closed)
        coroutine.send.assert_not_called()
        coroutine.close.assert_called_once_with()

    def test_when_coroutine_raises_then_it_is_not_silently_swallowed(self) -> None:
        subject = self._create_consumer(ThrowingCoroutine())

        with self.assertRaises(RuntimeError) as cm, subject:
            subject.send("a value")

        self.assertIn("boom", str(cm.exception))
        self.assertTrue(subject.closed)

    def test_when_worker_failed_then_further_sends_raise_the_error(self) -> None:
        subject = self._create_consumer(ThrowingCoroutine())

        try:
            subject.send("first")
        except RuntimeError:
            pass  # Synchronous backends surface the failure immediately.

        try:
            deadline = time.monotonic() + 5.0
            while True:
                try:
                    subject.send("another")
                except RuntimeError as e:
                    self.assertIn("boom", str(e))
                    break
                except WillNotConsume:
                    pass  # Queue full; the worker has not drained yet.
                if time.monotonic() > deadline:
                    self.fail("sends kept being accepted after the worker failed")
        finally:
            with suppress(RuntimeError):
                subject.close()
