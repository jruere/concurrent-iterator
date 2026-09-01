from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Iterator
from typing import Generic, TypeVar

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class StopIterationSentinel:
    """Sentinel to signal the end of data."""


class ExceptionInUserIterable:
    """User-provided iterable raises an exception."""

    def __init__(self, exception: BaseException) -> None:
        self.exception: BaseException = exception


class IProducer(Iterator[T_co], metaclass=ABCMeta):
    """Interface for Producers.

    Implementations of this interface are "normal" iterators that accept an
    iterator and return its values with the characteristic of running the given
    iterator in parallel and buffering a number of values.
    """

    @abstractmethod
    def __next__(self) -> T_co:
        pass


class WillNotConsume(Exception):
    """The consumer refuses to accept the given value."""


class IConsumer(Generic[T_contra], metaclass=ABCMeta):
    """Wraps coroutine like objects to execute them in parallel."""

    @abstractmethod
    def send(self, value: T_contra, timeout: float = 0) -> None:
        """Feeds a value to the consumer.

        :param value: Value to send.
        :param timeout: Time to wait to send value before failing if there's a
                        chance it might eventually succeed.
        :type timeout: float
        :returns: Nothing.
        :rtype: None
        :raises WillNotConsume: When the given value is not accepted. It may be
                                accepted on retry.
        """

    @abstractmethod
    def close(self) -> None:
        """Waits for the IConsumer to finish up and be destroyed."""

    @property
    @abstractmethod
    def closed(self) -> bool:
        """Whether the consumer has been closed."""
