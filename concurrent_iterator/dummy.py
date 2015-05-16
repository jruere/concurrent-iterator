# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals

from concurrent_iterator import IProducer, IConsumer
from concurrent_iterator.utils import check_open


class Producer(IProducer):
    """Dummy implementation that doesn't use concurrency."""

    def __init__(self, iterable):
        self._iterator = iter(iterable)

    def __next__(self):
        return next(self._iterator)

    def next(self):
        return self.__next__()


class Consumer(IConsumer):
    """Dummy implementation that doesn't use concurrency.

    The timeout parameter is ignored, this implementation will block forever.
    """

    def __init__(self, coroutine):
        self._coroutine = coroutine

        self._closed = False

    @check_open
    def send(self, value, timeout=0):
        self._coroutine.send(value)

    @check_open
    def close(self):
        self._closed = True  # Nothing to do.
        self._coroutine.close()

    @property
    def closed(self):
        return self._closed
