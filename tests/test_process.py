from __future__ import annotations

import itertools
import logging
import multiprocessing
import multiprocessing.managers
import time
import unittest
from collections.abc import Iterable, Iterator
from contextlib import closing
from typing import Any, TypeVar

from concurrent_iterator.process import Consumer, Producer
from tests import ConsumerTestMixin, ProducerTestMixin

T = TypeVar("T")

logging.basicConfig(level=logging.WARNING)


class ProcessProducerTest(unittest.TestCase):
    _orig_start_method: str | None

    def setUp(self) -> None:
        self._orig_start_method = multiprocessing.get_start_method()
        try:
            multiprocessing.set_start_method("fork", force=True)
        except ValueError:
            self.skipTest("fork start method not available")

    def tearDown(self) -> None:
        try:
            multiprocessing.set_start_method(self._orig_start_method, force=True)
        except Exception:  # noqa: BLE001, S110
            pass


class ProcessProducerTestChunk1(ProcessProducerTest, ProducerTestMixin):
    def _create_producer(self, iterable: Iterable[T]) -> Producer[T]:
        return Producer(iterable, chunksize=1)


class ProcessProducerTestChunk2(ProcessProducerTest, ProducerTestMixin):
    def _create_producer(self, iterable: Iterable[T]) -> Producer[T]:
        return Producer(iterable, chunksize=2)


class ProcessProducerValidationTest(ProcessProducerTest):
    def test_when_maxsize_invalid_then_assertion_error(self) -> None:
        with self.assertRaises(AssertionError):
            Producer(range(3), chunksize=1, maxsize=0)

        with self.assertRaises(AssertionError):
            Producer(range(3), chunksize=1, maxsize=-5)

        with self.assertRaises(AssertionError):
            Producer(range(3), chunksize=0, maxsize=5)

        with self.assertRaises(AssertionError):
            Producer(range(3), chunksize=-1, maxsize=5)

        with self.assertRaises(AssertionError):
            Producer(range(3), chunksize=5, maxsize=1)


class ProcessProducerFailureTest(ProcessProducerTest):
    def test_when_child_dies_then_next_raises_runtime_error(self) -> None:
        subject = Producer(itertools.count(), chunksize=1, maxsize=1)

        self.assertEqual(0, next(subject))
        # Allow background process to block on queue.put (queue full)
        time.sleep(0.3)

        self.assertEqual(1, next(subject))
        # Kill child while queue is empty

        subject._process.terminate()
        subject._process.join(timeout=1.0)

        self.assertFalse(subject._process.is_alive())

        t0 = time.time()

        with self.assertRaises(RuntimeError) as cm:
            next(subject)

        self.assertIn("Child process died", str(cm.exception))
        self.assertLess(time.time() - t0, 1.0, "should not hang")

        with self.assertRaises(RuntimeError):
            next(subject)

        subject.close()

    def test_when_child_dies_with_buffered_item_then_returns_buffer_before_raising(
        self,
    ) -> None:
        subject = Producer(itertools.count(), chunksize=1, maxsize=10)

        self.assertEqual(0, next(subject))
        time.sleep(0.3)

        subject._process.terminate()
        subject._process.join(timeout=1.0)
        # Should still be able to drain already-queued items before detecting death
        # With maxsize 10, at least a few items are buffered

        self.assertEqual(1, next(subject))
        # Eventually after draining, should raise RuntimeError, not hang forever

        raised = False
        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                next(subject)
            except RuntimeError:
                raised = True
                break
            except StopIteration:
                self.fail("should raise RuntimeError, not StopIteration")

        self.assertTrue(raised, "expected RuntimeError after child died")

        subject.close()


class ProcessConsumerTest(unittest.TestCase, ConsumerTestMixin):
    class Coroutine:
        def __init__(self) -> None:
            self.values: list[Any] = []
            self.closed = False

        def send(self, value: Any) -> None:
            self.values.append(value)

        def get_values(self) -> list[Any]:
            return list(self.values)

        def close(self) -> None:
            self.closed = True

        def get_closed(self) -> bool:
            return self.closed

    coroutine: Any

    def _create_consumer(self, coroutine: Any) -> Consumer[Any]:
        return Consumer(coroutine)

    def setUp(self) -> None:
        manager = multiprocessing.managers.BaseManager()
        manager.register("Coroutine", ProcessConsumerTest.Coroutine)
        manager.start()
        self.coroutine = manager.Coroutine()  # type: ignore[attr-defined]

    def test_when_a_value_is_sent_then_it_is_forwarded_to_the_coroutine(self) -> None:
        with closing(self._create_consumer(self.coroutine)) as subject:
            subject.send("a value")

        self.assertEqual(["a value"], self.coroutine.get_values())

    def test_when_closed_then_sending_should_not_work(self) -> None:
        subject = self._create_consumer(self.coroutine)

        subject.close()

        self.assertRaises(ValueError, subject.send, 0)
        self.assertEqual([], self.coroutine.get_values())

    def test_when_closed_then_closing_should_work(self) -> None:
        subject = self._create_consumer(self.coroutine)

        subject.close()
        subject.close()

        self.assertEqual([], self.coroutine.get_values())

    def test_when_closed_then_it_should_close_the_passed_coroutine(self) -> None:
        subject = self._create_consumer(self.coroutine)

        subject.close()

        self.assertTrue(self.coroutine.get_closed())


class ProcessConsumerCloseTest(unittest.TestCase):
    class SlowCoroutine:
        def __init__(self) -> None:
            self.values: list[Any] = []

        def send(self, value: Any) -> None:
            time.sleep(1.0)
            self.values.append(value)

        def get_values(self) -> list[Any]:
            return list(self.values)

        def close(self) -> None:
            pass

        def get_closed(self) -> bool:
            return False

    manager: Any

    def _create_consumer(self, coroutine: Any) -> Consumer[Any]:
        return Consumer(coroutine)

    def setUp(self) -> None:
        multiprocessing.set_start_method("fork", force=True)
        manager = multiprocessing.managers.BaseManager()
        manager.register("SlowCoroutine", ProcessConsumerCloseTest.SlowCoroutine)
        manager.start()
        self.manager = manager

    def test_when_queue_full_then_close_returns_quickly(self) -> None:
        # Coroutine that sleeps to keep queue full
        coro = self.manager.SlowCoroutine()
        subject: Consumer[Any] = Consumer(coro, maxsize=1)

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


class ProcessConsumerValidationTest(unittest.TestCase):
    def test_when_maxsize_invalid_then_assertion_error(self) -> None:
        manager = multiprocessing.managers.BaseManager()
        manager.register("Coroutine", ProcessConsumerTest.Coroutine)
        manager.start()
        coro = manager.Coroutine()  # type: ignore[attr-defined]

        with self.assertRaises(AssertionError):
            Consumer(coro, maxsize=1, shutdown_timeout_secs=0)

        with self.assertRaises(AssertionError):
            Consumer(coro, maxsize=1, shutdown_timeout_secs=-1)


def gen(count: int = 3) -> Iterator[int]:
    yield from range(count)


def throwing_gen() -> Iterator[int]:
    yield 1
    raise AssertionError("Test exception")


class ProcessStartMethodTest(unittest.TestCase):
    _orig_start_method: str | None

    def setUp(self) -> None:
        self._orig_start_method = multiprocessing.get_start_method()
        multiprocessing.set_start_method("fork", force=True)

    def tearDown(self) -> None:
        try:
            multiprocessing.set_start_method(self._orig_start_method, force=True)
        except Exception:  # noqa: BLE001, S110
            pass

    def test_producer_with_generator_under_fork(self) -> None:
        p = Producer(gen(), chunksize=1)

        self.assertEqual([0, 1, 2], list(p))

    def test_producer_with_throwing_generator_under_fork(self) -> None:
        p = Producer(throwing_gen(), chunksize=1)

        self.assertEqual(1, next(p))
        self.assertRaises(AssertionError, next, p)

    def test_producer_with_list_under_all_start_methods(self) -> None:
        for method in multiprocessing.get_all_start_methods():
            with self.subTest(start_method=method):
                multiprocessing.set_start_method(method, force=True)

                p = Producer(iter([1, 2, 3]), chunksize=1)
                actual = list(p)

                self.assertEqual([1, 2, 3], actual)

    def test_producer_with_generator_under_non_fork_raises_clear_error(self) -> None:
        for method in multiprocessing.get_all_start_methods():
            if method == "fork":
                continue
            with self.subTest(start_method=method):
                multiprocessing.set_start_method(method, force=True)

                with self.assertRaises(RuntimeError) as cm:
                    Producer(gen(), chunksize=1)

                self.assertIn("requires start method 'fork'", str(cm.exception))
                self.assertIn(method, str(cm.exception))
