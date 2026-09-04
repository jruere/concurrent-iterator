from __future__ import annotations

import logging
import unittest
from collections.abc import Iterable
from typing import Any, TypeVar

from concurrent_iterator import ConsumerCoroutine
from concurrent_iterator.dummy import Consumer, Producer
from tests import ConsumerTestMixin, ProducerTestMixin

T = TypeVar("T")

logging.basicConfig(level=logging.WARNING)


class DummyProducerTest(unittest.TestCase, ProducerTestMixin):
    def _create_producer(self, iterable: Iterable[T]) -> Producer[T]:
        return Producer(iterable)

    def test_when_generating_element_takes_time_then_it_should_be_faster_than_sequential(
        self,
    ) -> None:
        pass  # Disabled since the dummy implementation is not concurrent.


class DummyProducerValidationTest(unittest.TestCase):
    def test_when_maxsize_invalid_then_assertion_error(self) -> None:
        iterable = range(3)

        with self.assertRaises(AssertionError):
            Producer(iterable, maxsize=0)

        with self.assertRaises(AssertionError):
            Producer(iterable, maxsize=-5)


class DummyConsumerTest(unittest.TestCase, ConsumerTestMixin):
    def _create_consumer(self, coroutine: ConsumerCoroutine[Any]) -> Consumer[Any]:
        return Consumer(coroutine)
