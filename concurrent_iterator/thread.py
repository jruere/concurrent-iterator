# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals

import threading
try:
    # Python 3.
    from queue import Queue, Full
except ImportError:
    from Queue import Queue, Full

from concurrent_iterator import IProducer, IConsumer, StopIterationSentinel, WillNotConsume
from concurrent_iterator.utils import check_open


class Producer(IProducer):
    """Uses a thread to produce and buffer values from the given iterable.

    This implementation is useful for IO bound consumers.
    """

    def __init__(self, iterable, maxsize=100):
        iterator = iter(iterable)

        self._queue = Queue(maxsize)
        self._thread = threading.Thread(
            target=self._run, args=(iterator, self._queue))
        self._thread.daemon = True

        self._thread.start()

    def __next__(self):
        item = self._queue.get()
        if item is StopIterationSentinel:
            self._thread.join()
            raise StopIteration
        return item

    def next(self):
        return self.__next__()

    @staticmethod
    def _run(iterator, queue):
        for item in iterator:
            queue.put(item)
        queue.put(StopIterationSentinel)  # Signal we are done.


class Consumer(IConsumer):
    """Feeds the given coroutine in a separate thread."""

    def __init__(self, coroutine, maxsize=1):
        self._coroutine = coroutine

        self._closed = False
        self._queue = Queue(maxsize)
        self._thread = threading.Thread(
            target=self._run, args=(coroutine, self._queue))
        self._thread.daemon = True

        self._thread.start()

    @check_open
    def send(self, value, timeout=0):
        try:
            self._queue.put(value, block=(timeout != 0), timeout=timeout)
        except Full:
            raise WillNotConsume()

    @check_open
    def close(self):
        self._queue.put(StopIterationSentinel)
        self._thread.join()
        self._closed = True

    @property
    def closed(self):
        return self._closed

    @staticmethod
    def _run(coroutine, queue):
        for value in iter(queue.get, StopIterationSentinel):
            coroutine.send(value)
