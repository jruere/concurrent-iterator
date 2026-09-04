from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Literal, TypeVar

from concurrent_iterator import ConsumerCoroutine, IConsumer, IProducer
from concurrent_iterator._internal import check_open

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class Producer(IProducer[T_co]):
    """Dummy implementation that doesn't use concurrency."""

    def __init__(self, iterable: Iterable[T_co], maxsize: int | None = None) -> None:
        """In this implementation, `maxsize` is included to ease replacing
        implementations but it's ignored.
        """
        assert (
            maxsize is None or maxsize > 0
        ), f"`maxsize` must be None or positive, but is {maxsize}."

        self._iterator = iter(iterable)

        self._closed = False

    def __next__(self) -> T_co:
        if self._closed:
            raise StopIteration

        try:
            return next(self._iterator)
        except Exception:
            self.close()
            raise

    def __iter__(self) -> Iterator[T_co]:
        return self

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> Producer[T_co]:
        return self

    def __exit__(self, *_: object) -> Literal[False]:
        self.close()
        return False


class Consumer(IConsumer[T_contra]):
    """Dummy implementation that doesn't use concurrency."""

    def __init__(self, coroutine: ConsumerCoroutine[T_contra]) -> None:
        self._coroutine = coroutine

        self._closed = False

    @check_open
    def send(self, value: T_contra, timeout: float = 0) -> None:
        """`timeout` is not supported and fails if greater than 0."""
        assert timeout in (0, 0.0), f"`timeout` is not supported in this implementation: {timeout}."

        self._coroutine.send(value)

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        self._coroutine.close()

    @property
    def closed(self) -> bool:
        return self._closed

    def __enter__(self) -> Consumer[T_contra]:
        return self

    def __exit__(self, *_: object) -> Literal[False]:
        self.close()
        return False
