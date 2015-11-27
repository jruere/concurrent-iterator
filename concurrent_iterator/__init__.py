# vim: set fileencoding=utf-8
from abc import ABCMeta, abstractmethod, abstractproperty
from collections import Iterator


__version__ = '0.2.4'


class StopIterationSentinel(object):
    """Sentinel to signal the end of data."""

class ExceptionInUserIterable(object):
    """User-provided iterable raises an exception."""

    def __init__(self, exception):
        self.exception = exception

class IProducer(Iterator):
    """Interface for Producers.

    Implementations of this interface are "normal" iterators that accept an
    iterator and return its values with the characteristic of running the given
    iterator in parallel and buffering a number of values.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def __next__(self):
        pass


class WillNotConsume(Exception):
    """The consumer refuses to accept the given value."""


class IConsumer(object):
    """Wraps coroutine like objects to execute them in parallel."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def send(self, value, timeout=0):
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
    def close(self):
        """Waits for the IConsumer to finish up and be destroyed."""

    @abstractproperty
    def closed(self):
        """Whether the consumer has been closed."""
