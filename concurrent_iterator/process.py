# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals

import itertools
import logging
import multiprocessing
try:
    from queue import Full
except ImportError:
    from Queue import Full

from concurrent_iterator import (
    ExceptionInUserIterable,
    IProducer,
    IConsumer,
    StopIterationSentinel,
    WillNotConsume,
)
from concurrent_iterator.utils import check_open


class Producer(IProducer):
    """Uses a separate process to produce and buffer values from the given
    iterable.

    This implementation is useful for IO or CPU bound consumers.

    See multiprocessing.Pool for a more useful abstraction for CPU bound
    producers.

    For logging to work properly, use multiprocessing-logging.
    """

    def __init__(self, iterable, maxsize=100, chunksize=1):
        assert chunksize > 0
        assert maxsize >= chunksize

        self._iterator = iter(iterable)

        self._queue = multiprocessing.Queue(maxsize // chunksize)
        self._process = multiprocessing.Process(
            target=Producer._run,
            args=(self._iterator, self._queue, chunksize),
        )
        self._process.daemon = True
        self._current_chunk = None
        self._log = logging.getLogger(__name__ + '.' + type(self).__name__)

        self._log.info("Starting process.")
        self._process.start()

    def __next__(self):
        if self._current_chunk:
            pass
        elif not self._queue:
            self._log.debug("Producer is exhausted.")
            raise StopIteration
        else:
            chunk = self._queue.get()
            if chunk == StopIterationSentinel:
                self._process.join()

                self._queue.close()
                self._queue = None
                raise StopIteration
            else:
                assert chunk
                chunk.reverse()  # To consume it from the end.
                self._current_chunk = chunk

        item = self._current_chunk.pop()
        if isinstance(item, ExceptionInUserIterable):
            self._process.join()

            self._queue.close()
            self._queue = None

            raise item.exception

        return item

    def next(self):
        return self.__next__()

    @staticmethod
    def _run(iterator, queue, chunksize):
        chunk = []
        try:
            while True:
                chunk = []
                for item in itertools.islice(iterator, chunksize):
                    chunk.append(item)
                if not chunk:
                    queue.put(StopIterationSentinel)  # Signal we are done.
                    break
                else:
                    queue.put(chunk)
        except Exception as e:
            chunk.append(ExceptionInUserIterable(e))
            queue.put(chunk)
            queue.close()
            queue.join_thread()

            # Per PEP 255, this terminates the iterable.


class Consumer(IConsumer):
    """Feeds the given coroutine in a separate process."""

    def __init__(self, coroutine, maxsize=1):
        self._coroutine = coroutine

        self._closed = False
        self._queue = multiprocessing.Queue(maxsize)
        self._process = multiprocessing.Process(
            target=self._run, args=(coroutine, self._queue))
        self._process.daemon = True

        self._process.start()

    @check_open
    def send(self, value, timeout=0):
        try:
            self._queue.put(value, block=(timeout != 0), timeout=timeout)
        except Full:
            raise WillNotConsume()

    @check_open
    def close(self):
        self._closed = True
        self._queue.put(StopIterationSentinel)
        self._process.join()

    @property
    def closed(self):
        return self._closed

    @staticmethod
    def _run(coroutine, queue):
        for value in iter(queue.get, StopIterationSentinel):
            coroutine.send(value)
        coroutine.close()
