# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals

import collections
import logging
import multiprocessing
import Queue


class SpawnedIterator(collections.Iterator):
    """Uses a separate process to produce and buffer values from the given
    iterable.

    This implementation is useful for IO or CPU bound consumers.

    See multiprocessing.Pool for a more useful abstraction for CPU bound
    producers.

    For logging to work properly, use multiprocessing-logging.
    """

    _SENTINEL = b"STOP SENTINEL"

    def __init__(self, iterable, maxsize=100):
        self._iterator = iter(iterable)

        self._queue = multiprocessing.Queue(maxsize)
        self._process = multiprocessing.Process(
            target=SpawnedIterator._run, args=(self._iterator, self._queue))
        self._process.daemon = True
        self._log = logging.getLogger(__name__ + '.' + type(self).__name__)

        self._log.info("Starting process.")
        self._process.start()

    def __next__(self):
        while self._queue or self._process.is_alive():
            try:
                item = self._queue.get(timeout=0.01)
                if item == SpawnedIterator._SENTINEL:
                    self._process.join()
                    raise StopIteration
                return item
            except Queue.Empty:
                pass
        self._log.debug("Producer is exhausted.")
        raise StopIteration

    def next(self):
        return self.__next__()

    @staticmethod
    def _run(iterator, queue):
        for item in iterator:
            queue.put(item)
        queue.put(SpawnedIterator._SENTINEL)