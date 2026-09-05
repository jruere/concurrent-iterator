from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from concurrent_iterator import ConsumerCoroutine
from concurrent_iterator._abc import BaseConsumer, BaseProducer
from concurrent_iterator._internal import check_open

T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class Producer(BaseProducer[T_co]):
    """Dummy implementation that doesn't use concurrency."""

    def __init__(self, iterable: Iterable[T_co], maxsize: int | None = None) -> None:
        """In this implementation, `maxsize` is included to ease replacing
        implementations but it's ignored.
        """
        assert (
            maxsize is None or maxsize > 0
        ), f"`maxsize` must be None or positive, but is {maxsize}."

        super().__init__()
        self._iterator = iter(iterable)

    def __next__(self) -> T_co:
        if self._closed:
            raise StopIteration

        try:
            return next(self._iterator)
        except Exception:
            self.close()
            raise

    def _do_close(self) -> None:
        pass


class Consumer(BaseConsumer[T_contra]):
    """Dummy implementation that doesn't use concurrency."""

    def __init__(self, coroutine: ConsumerCoroutine[T_contra]) -> None:
        super().__init__()
        self._coroutine = coroutine

    @check_open
    def send(self, value: T_contra, timeout: float = 0) -> None:
        """`timeout` is not supported and fails if greater than 0."""
        assert timeout in (0, 0.0), f"`timeout` is not supported in this implementation: {timeout}."

        self._coroutine.send(value)

    def _do_close(self) -> None:
        self._coroutine.close()
