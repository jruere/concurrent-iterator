from __future__ import annotations

import threading
from collections.abc import Iterable, Iterator
from queue import Full, Queue
from typing import Any, TypeVar, cast

from concurrent_iterator import (
    ExceptionInUserIterable,
    IConsumer,
    IProducer,
    StopIterationSentinel,
    WillNotConsume,
)
from concurrent_iterator.utils import check_open

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class MultiProducer(IProducer[T_co]):
    """Uses a thread to produce and buffer values from several iterables.

    This is different from merging multiple independent producers in that
    `maxsize` limit applies to the total output, not individual producers.

    Exceptions terminate a generator (PEP 255) but in this case we have multiple
    generators. The way this is resolved is that the first generator to raise an
    exception terminates the entire MultiProducer.
    The rationale for this is to prevent hiding exceptions.

    This implementation is useful for IO bound consumers.
    """

    def __init__(self, iterables: Iterable[Iterable[T_co]], maxsize: int = 100) -> None:
        self._queue: Queue[object] = Queue(maxsize)
        self._threads: list[threading.Thread] = []

        self._spawn_workers(iterables)
        self._active_threads: int = len(self._threads)

    def _spawn_workers(self, iterables: Iterable[Iterable[T_co]]) -> None:
        for iterable in iterables:
            thread = threading.Thread(target=self._run, args=(iter(iterable), self._queue))
            thread.daemon = True
            thread.start()

            self._threads.append(thread)

    def __next__(self) -> T_co:
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
                return cast(T_co, item)

    def next(self) -> T_co:
        return self.__next__()

    @staticmethod
    def _run(iterator: Iterator[T_co], queue: Queue[object]) -> None:
        while True:
            try:
                item = next(iterator)
                queue.put(item)
            except StopIteration:
                queue.put(StopIterationSentinel)  # Signal we are done.
                break
            except Exception as e:  # noqa: BLE001  # intentional: forward user iterable exception
                queue.put(ExceptionInUserIterable(e))

                # Per PEP 255, this terminates the iterable.
                break


class Producer(MultiProducer[T_co]):
    """Uses a thread to produce and buffer values from the given iterable.

    This implementation is useful for IO bound consumers.
    """

    def __init__(self, iterable: Iterable[T_co], maxsize: int = 100) -> None:
        super().__init__([iterable], maxsize)


class Consumer(IConsumer[T_contra]):
    """Feeds the given coroutine in a separate thread."""

    def __init__(self, coroutine: Any, maxsize: int = 1) -> None:
        self._coroutine: Any = coroutine

        self._closed: bool = False
        self._queue: Queue[object] = Queue(maxsize)
        self._thread: threading.Thread = threading.Thread(
            target=self._run, args=(coroutine, self._queue)
        )
        self._thread.daemon = True

        self._thread.start()

    @check_open
    def send(self, value: T_contra, timeout: float = 0) -> None:
        try:
            self._queue.put(value, block=(timeout != 0), timeout=timeout)
        except Full:
            raise WillNotConsume()

    @check_open
    def close(self) -> None:
        self._closed = True
        self._queue.put(StopIterationSentinel)
        self._thread.join()

    @property
    def closed(self) -> bool:
        return self._closed

    @staticmethod
    def _run(coroutine: Any, queue: Queue[object]) -> None:
        for value in iter(queue.get, StopIterationSentinel):
            coroutine.send(value)
        coroutine.close()
