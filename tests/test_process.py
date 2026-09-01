import logging
import multiprocessing
import multiprocessing.managers
import unittest
from contextlib import closing

from concurrent_iterator.process import Consumer, Producer
from tests import ProducerTestMixin

logging.basicConfig(level=logging.DEBUG)


class ProcessProducerTest(unittest.TestCase):
    def setUp(self):
        self._orig_start_method = multiprocessing.get_start_method()
        try:
            multiprocessing.set_start_method("fork", force=True)
        except ValueError:
            self.skipTest("fork start method not available")

    def tearDown(self):
        try:
            multiprocessing.set_start_method(self._orig_start_method, force=True)
        except Exception:  # noqa: BLE001, S110
            pass


class ProcessProducerTestChunk1(ProcessProducerTest, ProducerTestMixin):

    def _create_producer(self, iterable):
        return Producer(iterable, chunksize=1)


class ProcessProducerTestChunk2(ProcessProducerTest, ProducerTestMixin):

    def _create_producer(self, iterable):
        return Producer(iterable, chunksize=2)


class ProcessConsumerTest(unittest.TestCase):

    class Coroutine:

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
        manager.register("Coroutine", ProcessConsumerTest.Coroutine)
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


def gen(count=3):
    yield from range(count)


def throwing_gen():
    yield 1
    raise AssertionError("Test exception")


class ProcessStartMethodTest(unittest.TestCase):
    def setUp(self):
        self._orig_start_method = multiprocessing.get_start_method()
        multiprocessing.set_start_method("fork", force=True)

    def tearDown(self):
        try:
            multiprocessing.set_start_method(self._orig_start_method, force=True)
        except Exception:  # noqa: BLE001, S110
            pass

    def test_producer_with_generator_under_fork(self):
        p = Producer(gen(), chunksize=1)

        self.assertEqual([0, 1, 2], list(p))

    def test_producer_with_throwing_generator_under_fork(self):
        p = Producer(throwing_gen(), chunksize=1)

        self.assertEqual(1, next(p))
        self.assertRaises(AssertionError, next, p)

    def test_producer_with_list_under_all_start_methods(self):
        for method in multiprocessing.get_all_start_methods():
            with self.subTest(start_method=method):
                multiprocessing.set_start_method(method, force=True)

                p = Producer(iter([1, 2, 3]), chunksize=1)
                actual = list(p)

                self.assertEqual([1, 2, 3], actual)

    def test_producer_with_generator_under_non_fork_raises_clear_error(self):
        for method in multiprocessing.get_all_start_methods():
            if method == "fork":
                continue
            with self.subTest(start_method=method):
                multiprocessing.set_start_method(method, force=True)

                with self.assertRaises(RuntimeError) as cm:
                    Producer(gen(), chunksize=1)

                self.assertIn("requires start method 'fork'", str(cm.exception))
                self.assertIn(method, str(cm.exception))
