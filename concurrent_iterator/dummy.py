from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any, TypeVar

from concurrent_iterator import IConsumer, IProducer
from concurrent_iterator.utils import check_open

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class Producer(IProducer[T_co]):
    """Dummy implementation that doesn't use concurrency."""

    def __init__(self, iterable: Iterable[T_co], maxsize: int | None = None) -> None:
        """In this implementation, maxsize is included to ease replacing
        implementations but it's ignored.
        """
        self._iterator = iter(iterable)

    def __next__(self) -> T_co:
        return next(self._iterator)

    def __iter__(self) -> Iterator[T_co]:
        return self


class Consumer(IConsumer[T_contra]):
    """Dummy implementation that doesn't use concurrency.

    The timeout parameter is ignored, this implementation will block forever.
    """

    def __init__(self, coroutine: Any) -> None:
        self._coroutine = coroutine

        self._closed = False

    @check_open
    def send(self, value: T_contra, timeout: float = 0) -> None:
        self._coroutine.send(value)

    @check_open
    def close(self) -> None:
        self._closed = True  # Nothing to do.
        self._coroutine.close()

    @property
    def closed(self) -> bool:
        return self._closed
