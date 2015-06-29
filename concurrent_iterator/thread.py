# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals

import threading
try:
    # Python 3.
    from queue import Queue, Full
except ImportError:
    from Queue import Queue, Full

from concurrent_iterator import (
    ExceptionInUserIterable,
    IProducer,
    IConsumer,
    StopIterationSentinel,
    WillNotConsume,
)
from concurrent_iterator.utils import check_open


class MultiProducer(IProducer):
    """Uses a thread to produce and buffer values from several iterables.

    This is different from merging multiple independent producers in that
    `maxsize` limit applies to the total output, not individual producers.

    Exceptions terminate a generator (PEP 255) but in this case we have multiple
    generators. The way this is resolved is that the first generator to raise an
    exception terminates the entire MultiProducer.
    The rationale for this is to prevent hiding exceptions.

    This implementation is useful for IO bound consumers.
    """

    def __init__(self, iterables, maxsize=100):
        self._queue = Queue(maxsize)
        self._threads = []

        self._spawn_workers(iterables)
        self._active_threads = len(self._threads)

    def _spawn_workers(self, iterables):
        for iterable in iterables:
            thread = threading.Thread(
                target=self._run, args=(iter(iterable), self._queue))
            thread.daemon = True
            thread.start()

            self._threads.append(thread)

    def __next__(self):
        if not self._active_threads:
            # This producer is exhausted.
            raise StopIteration

        while True:
            item = self._queue.get()
            if item is StopIterationSentinel:
                self._active_threads -= 1
                if not self._active_threads:
                    for thread in self._threads:
                        thread.join()

                    raise StopIteration
            elif isinstance(item, ExceptionInUserIterable):
                # Any generator raising an exception terminates the entire
                # MultiProducer as generators don't continue after an exception.
                self._active_threads = 0
                raise item.exception
            else:
                return item

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


class Producer(MultiProducer):
    """Uses a thread to produce and buffer values from the given iterable.

    This implementation is useful for IO bound consumers.
    """

    def __init__(self, iterable, maxsize=100):
        super(Producer, self).__init__([iterable], maxsize)


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
        self._closed = True
        self._queue.put(StopIterationSentinel)
        self._thread.join()

    @property
    def closed(self):
        return self._closed

    @staticmethod
    def _run(coroutine, queue):
        for value in iter(queue.get, StopIterationSentinel):
            coroutine.send(value)
        coroutine.close()
