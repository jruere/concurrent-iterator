# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals

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

    def __init__(self, iterable, maxsize=100):
        self._iterator = iter(iterable)

        self._queue = multiprocessing.Queue(maxsize)
        self._process = multiprocessing.Process(
            target=Producer._run, args=(self._iterator, self._queue))
        self._process.daemon = True
        self._log = logging.getLogger(__name__ + '.' + type(self).__name__)

        self._log.info("Starting process.")
        self._process.start()

    def __next__(self):
        while self._queue:
            item = self._queue.get()
            if item == StopIterationSentinel:
                self._process.join()

                self._queue.close()
                self._queue = None
            elif isinstance(item, ExceptionInUserIterable):
                self._process.terminate()
                self._process.join()

                self._queue.close()
                self._queue = None

                raise item.exception
            else:
                return item
        self._log.debug("Producer is exhausted.")
        raise StopIteration

    def next(self):
        return self.__next__()

    @staticmethod
    def _run(iterator, queue):
        while True:
            try:
                item = next(iterator)
                queue.put(item)
            except StopIteration:
                queue.put(StopIterationSentinel)  # Signal we are done.
                break
            except Exception as e:
                queue.put(ExceptionInUserIterable(e))

                # Per PEP 255, this terminates the iterable.
                break


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
