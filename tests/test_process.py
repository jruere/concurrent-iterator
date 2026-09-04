from __future__ import annotations

import itertools
import logging
import multiprocessing
import multiprocessing.managers
import time
import unittest
from collections.abc import Iterable, Iterator
from contextlib import closing
from multiprocessing.context import BaseContext
from typing import Any, ClassVar, TypeVar

from concurrent_iterator import ConsumerCoroutine
from concurrent_iterator.process import Consumer, Producer
from tests import ConsumerTestMixin, ProducerTestMixin

T = TypeVar("T")

logging.basicConfig(level=logging.WARNING)


class ProcessProducerTest(unittest.TestCase):
    fork_mp_context: ClassVar[BaseContext]

    @classmethod
    def setUpClass(cls) -> None:
        cls.fork_mp_context = multiprocessing.get_context("fork")


class ProcessProducerTestChunk1(ProcessProducerTest, ProducerTestMixin):
    def _create_producer(self, iterable: Iterable[T]) -> Producer[T]:
        return Producer(iterable, chunksize=1, mp_context=self.fork_mp_context)


class ProcessProducerTestChunk2(ProcessProducerTest, ProducerTestMixin):
    def _create_producer(self, iterable: Iterable[T]) -> Producer[T]:
        return Producer(iterable, chunksize=2, mp_context=self.fork_mp_context)


class ProcessProducerValidationTest(ProcessProducerTest):
    def test_when_maxsize_invalid_then_assertion_error(self) -> None:
        with self.assertRaises(AssertionError):
            Producer(range(3), chunksize=1, maxsize=0)

        with self.assertRaises(AssertionError):
            Producer(range(3), chunksize=1, maxsize=-5)

    def test_when_chunksize_invalid_then_assertion_error(self) -> None:
        with self.assertRaises(AssertionError):
            Producer(range(3), chunksize=0, maxsize=5)

        with self.assertRaises(AssertionError):
            Producer(range(3), chunksize=-1, maxsize=5)

    def test_when_chunksize_larger_than_maxsize_then_assertion_error(self) -> None:
        with self.assertRaises(AssertionError):
            Producer(range(3), chunksize=5, maxsize=1)


class ProcessProducerFailureTest(ProcessProducerTest):
    def test_when_child_dies_then_next_raises_runtime_error(self) -> None:
        gate = self.fork_mp_context.Event()

        def gated_count() -> Iterator[int]:
            yield 0
            # Block so the child cannot buffer anything past the consumed item.
            # Timeout only bounds pathological runs; the child is terminated below.
            gate.wait(10.0)
            yield from itertools.count(1)

        subject = Producer(gated_count(), chunksize=1, maxsize=1, mp_context=self.fork_mp_context)

        self.assertEqual(0, next(subject))
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
        subject = Producer(
            itertools.count(), chunksize=1, maxsize=10, mp_context=self.fork_mp_context
        )

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

    coroutine: Coroutine

    def _create_consumer(self, coroutine: ConsumerCoroutine[Any]) -> Consumer[Any]:
        fork_ctx = multiprocessing.get_context("fork")
        return Consumer(coroutine, mp_context=fork_ctx)

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

    def test_when_close_called_twice_then_idempotent(self) -> None:
        subject = self._create_consumer(self.coroutine)

        subject.close()
        subject.close()

        self.assertTrue(subject.closed)
        self.assertEqual([], self.coroutine.get_values())
        self.assertTrue(self.coroutine.get_closed())

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

    def _create_consumer(self, coroutine: ConsumerCoroutine[Any]) -> Consumer[Any]:
        fork_ctx = multiprocessing.get_context("fork")
        return Consumer(coroutine, mp_context=fork_ctx)

    def setUp(self) -> None:
        manager = multiprocessing.managers.BaseManager()
        manager.register("SlowCoroutine", ProcessConsumerCloseTest.SlowCoroutine)
        manager.start()
        self.manager = manager

    def test_when_queue_full_then_close_returns_quickly(self) -> None:
        # Coroutine that sleeps to keep queue full
        coro = self.manager.SlowCoroutine()
        subject: Consumer[Any] = self._create_consumer(coro)

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
            Consumer(coro, maxsize=0)

        with self.assertRaises(AssertionError):
            Consumer(coro, maxsize=-5)

    def test_when_shutdown_timeout_invalid_then_assertion_error(self) -> None:
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


class ProcessMpContextTest(unittest.TestCase):
    def test_when_default_then_it_follows_the_global_setting(self) -> None:
        try:
            multiprocessing.get_context("spawn")
        except ValueError:
            self.skipTest("spawn start method not available")

        orig = multiprocessing.get_start_method()
        multiprocessing.set_start_method("spawn", force=True)
        try:
            subject = Producer(iter([1, 2, 3]), chunksize=1)

            self.assertEqual([1, 2, 3], list(subject))

            with self.assertRaises(RuntimeError) as cm:
                Producer(gen(), chunksize=1)

            self.assertIn("requires start method 'fork'", str(cm.exception))
            self.assertIn("spawn", str(cm.exception))
        finally:
            multiprocessing.set_start_method(orig, force=True)

    def test_when_throwing_generator_under_fork_then_it_forwards_exception(self) -> None:
        try:
            fork_ctx = multiprocessing.get_context("fork")
        except ValueError:
            self.skipTest("fork start method not available")

        subject = Producer(throwing_gen(), chunksize=1, mp_context=fork_ctx)

        self.assertEqual(1, next(subject))
        self.assertRaises(AssertionError, next, subject)

    def test_when_picklable_under_all_mp_contexts_then_it_works(self) -> None:
        for method in multiprocessing.get_all_start_methods():
            with self.subTest(mp_context=method):
                ctx = multiprocessing.get_context(method)

                subject = Producer(iter([1, 2, 3]), chunksize=1, mp_context=ctx)

                self.assertEqual([1, 2, 3], list(subject))

    def test_when_generator_under_non_fork_mp_context_then_it_raises_clear_error(self) -> None:
        for method in multiprocessing.get_all_start_methods():
            if method == "fork":
                continue
            with self.subTest(mp_context=method):
                ctx = multiprocessing.get_context(method)

                with self.assertRaises(RuntimeError) as cm:
                    Producer(gen(), chunksize=1, mp_context=ctx)

                self.assertIn("requires start method 'fork'", str(cm.exception))
                self.assertIn(method, str(cm.exception))

    def test_when_local_differs_from_global_then_local_wins(self) -> None:
        try:
            fork_ctx = multiprocessing.get_context("fork")
            multiprocessing.get_context("spawn")
        except ValueError:
            self.skipTest("fork and spawn start methods required")

        orig = multiprocessing.get_start_method()
        multiprocessing.set_start_method("spawn", force=True)
        try:
            subject = Producer(gen(), chunksize=1, mp_context=fork_ctx)

            self.assertEqual([0, 1, 2], list(subject))

            spawn_ctx = multiprocessing.get_context("spawn")

            subject = Producer(iter([1, 2, 3]), chunksize=1, mp_context=spawn_ctx)

            self.assertEqual([1, 2, 3], list(subject))
        finally:
            multiprocessing.set_start_method(orig, force=True)

    def test_when_consumer_mp_context_spawn_then_it_forwards(self) -> None:
        try:
            spawn_ctx = multiprocessing.get_context("spawn")
        except ValueError:
            self.skipTest("spawn start method not available")

        manager = multiprocessing.managers.BaseManager()
        manager.register("Coroutine", ProcessConsumerTest.Coroutine)
        manager.start()
        coro = manager.Coroutine()  # type: ignore[attr-defined]

        subject = Consumer(coro, mp_context=spawn_ctx)

        subject.send("a value")
        subject.close()

        self.assertEqual(["a value"], coro.get_values())
