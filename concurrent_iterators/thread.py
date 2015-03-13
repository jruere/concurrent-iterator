# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals

import collections
import threading
try:
    from queue import Queue
except ImportError:
    from Queue import Queue


class SpawnedIterator(collections.Iterator):
    """Uses a thread to produce and buffer values from the given iterable.

    This implementation is useful for IO bound consumers.
    """

    _SENTINEL = object()

    def __init__(self, iterable, maxsize=100):
        iterator = iter(iterable)

        self._queue = Queue(maxsize)
        self._thread = threading.Thread(
            target=self._run, args=(iterator, self._queue))
        self._thread.daemon = True

        self._thread.start()

    def __next__(self):
        item = self._queue.get()
        if item is SpawnedIterator._SENTINEL:
            self._thread.join()
            raise StopIteration
        return item

    def next(self):
        return self.__next__()

    @staticmethod
    def _run(iterator, queue):
        for item in iterator:
            queue.put(item)
        queue.put(SpawnedIterator._SENTINEL)  # Signal we are done.
