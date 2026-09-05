from __future__ import annotations

import unittest
from collections.abc import Iterator
from typing import Any

from concurrent_iterator import IConsumer, IProducer
from concurrent_iterator._abc import BaseConsumer, BaseProducer


class StubProducer(BaseProducer[int]):
    def __init__(self) -> None:
        super().__init__()

        self.close_calls = 0

    def __next__(self) -> int:
        if self.closed:
            raise StopIteration

        raise StopIteration

    def _do_close(self) -> None:
        self.close_calls += 1


class StubConsumer(BaseConsumer[str]):
    def __init__(self) -> None:
        super().__init__()

        self.close_calls = 0

    def send(self, value: str, timeout: float = 0) -> None:
        assert timeout >= 0, f"`timeout` must be non-negative, but is {timeout}."

    def _do_close(self) -> None:
        self.close_calls += 1


class BaseProducerTest(unittest.TestCase):
    def test_when_created_then_not_closed(self) -> None:
        subject = StubProducer()

        self.assertFalse(subject.closed)

    def test_when_iter_called_then_returns_self(self) -> None:
        subject = StubProducer()

        result = iter(subject)

        self.assertIs(subject, result)

    def test_when_closed_then_closed_true_and_do_close_once(self) -> None:
        subject = StubProducer()

        subject.close()
        subject.close()

        self.assertTrue(subject.closed)
        self.assertEqual(1, subject.close_calls)

    def test_when_used_as_context_manager_then_closed_on_exit(self) -> None:
        subject = StubProducer()

        with subject:
            self.assertFalse(subject.closed)

        self.assertTrue(subject.closed)
        self.assertEqual(1, subject.close_calls)

    def test_when_exit_returns_then_is_false(self) -> None:
        subject = StubProducer()

        result = subject.__exit__(None, None, None)

        self.assertFalse(result)
        self.assertTrue(subject.closed)

    def test_when_del_called_then_closes(self) -> None:
        subject = StubProducer()

        subject.__del__()

        self.assertTrue(subject.closed)
        self.assertEqual(1, subject.close_calls)

    def test_when_init_failed_then_del_does_not_raise(self) -> None:
        subject = StubProducer.__new__(StubProducer)

        try:
            subject.__del__()
        except Exception as e:  # noqa: BLE001
            self.fail(f"__del__ raised {e!r}")

    def test_when_subclassed_then_is_iproducer(self) -> None:
        subject = StubProducer()

        self.assertIsInstance(subject, IProducer)
        self.assertIsInstance(subject, Iterator)


class BaseConsumerTest(unittest.TestCase):
    def test_when_created_then_not_closed(self) -> None:
        subject = StubConsumer()

        self.assertFalse(subject.closed)

    def test_when_closed_then_closed_true_and_do_close_once(self) -> None:
        subject = StubConsumer()

        subject.close()
        subject.close()

        self.assertTrue(subject.closed)
        self.assertEqual(1, subject.close_calls)

    def test_when_used_as_context_manager_then_closed_on_exit(self) -> None:
        with StubConsumer() as subject:
            self.assertFalse(subject.closed)

        self.assertTrue(subject.closed)

    def test_when_error_set_then_close_reraises(self) -> None:
        subject = StubConsumer()
        subject._error = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            subject.close()

        self.assertTrue(subject.closed)

    def test_when_del_called_then_closes(self) -> None:
        subject = StubConsumer()

        subject.__del__()

        self.assertTrue(subject.closed)
        self.assertEqual(1, subject.close_calls)

    def test_when_subclassed_then_is_iconsumer(self) -> None:
        subject: Any = StubConsumer()

        self.assertIsInstance(subject, IConsumer)


if __name__ == "__main__":
    unittest.main()
