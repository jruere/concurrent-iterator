from __future__ import annotations

import itertools
import logging
import multiprocessing
import multiprocessing.queues
import pickle
from collections.abc import Iterable, Iterator
from queue import Full
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


class Producer(IProducer[T_co]):
    """Uses a separate process to produce and buffer values from the given
    iterable.

    This implementation is useful for IO or CPU bound consumers.

    See multiprocessing.Pool for a more useful abstraction for CPU bound
    producers.

    For logging to work properly, use multiprocessing-logging.
    """

    def __init__(self, iterable: Iterable[T_co], maxsize: int = 100, chunksize: int = 1) -> None:
        assert chunksize > 0
        assert maxsize >= chunksize

        self._iterator: Iterator[T_co] = iter(iterable)

        self._queue: Any = multiprocessing.Queue(maxsize // chunksize)
        self._process: multiprocessing.Process = multiprocessing.Process(
            target=self._run,
            args=(self._iterator, self._queue, chunksize),
        )
        self._process.daemon = True
        self._current_chunk: list[Any] | None = None
        self._log: logging.Logger = logging.getLogger(__name__ + "." + type(self).__name__)

        self._log.info("Starting process.")
        try:
            self._process.start()
        except (TypeError, pickle.PicklingError) as e:
            if multiprocessing.get_start_method() != "fork":
                raise RuntimeError(
                    "process.Producer with generators and other unpicklable "
                    "iterables requires start method 'fork', got "
                    f"'{multiprocessing.get_start_method()}' (Python 3.14 defaults to 'forkserver'). Use "
                    "thread.Producer, a picklable iterable, or "
                    "multiprocessing.set_start_method('fork', force=True) / "
                    "multiprocessing.get_context('fork')."
                ) from e
            raise

    def __next__(self) -> T_co:
        if self._current_chunk:
            pass
        elif self._queue is None:
            self._log.debug("Producer is exhausted.")
            raise StopIteration
        else:
            chunk: Any = self._queue.get()
            if chunk is StopIterationSentinel or chunk == StopIterationSentinel:
                self._process.join()

                assert self._queue is not None
                self._queue.close()
                self._queue = None
                raise StopIteration
            else:
                assert chunk
                chunk.reverse()  # To consume it from the end.
                self._current_chunk = chunk

        assert self._current_chunk is not None
        item: Any = self._current_chunk.pop()
        if isinstance(item, ExceptionInUserIterable):
            self._process.join()

            if self._queue is not None:
                self._queue.close()
                self._queue = None

            raise item.exception

        return cast(T_co, item)

    def next(self) -> T_co:
        return self.__next__()

    def _run(self, iterator: Iterator[T_co], queue: Any, chunksize: int) -> None:
        chunk: list[Any] = []
        try:
            while True:
                # Items must be added one at a time to avoid losing items
                # before an exception.
                chunk.extend(itertools.islice(iterator, chunksize))
                if not chunk:
                    queue.put(StopIterationSentinel)  # Signal we are done.
                    break
                else:
                    queue.put(chunk)
                chunk = []
        except Exception as e:  # noqa: BLE001  # intentional: forward user iterable exception
            self._log.exception("Exception on iterator.")

            chunk.append(ExceptionInUserIterable(e))
            queue.put(chunk)
            queue.close()
            queue.join_thread()

            # Per PEP 255, this terminates the iterable.


class Consumer(IConsumer[T_contra]):
    """Feeds the given coroutine in a separate process."""

    def __init__(self, coroutine: Any, maxsize: int = 1) -> None:
        self._coroutine: Any = coroutine

        self._closed: bool = False
        self._queue: Any = multiprocessing.Queue(maxsize)
        self._process: multiprocessing.Process = multiprocessing.Process(
            target=self._run, args=(coroutine, self._queue)
        )
        self._process.daemon = True

        try:
            self._process.start()
        except (TypeError, pickle.PicklingError) as e:
            if multiprocessing.get_start_method() != "fork":
                raise RuntimeError(
                    "process.Consumer with unpicklable coroutines requires "
                    f"start method 'fork', got '{multiprocessing.get_start_method()}' (Python 3.14 defaults to "
                    "'forkserver'). Use thread.Consumer or "
                    "multiprocessing.set_start_method('fork', force=True) / "
                    "multiprocessing.get_context('fork')."
                ) from e
            raise

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
        self._process.join()

    @property
    def closed(self) -> bool:
        return self._closed

    @staticmethod
    def _run(coroutine: Any, queue: Any) -> None:
        for value in iter(queue.get, StopIterationSentinel):
            coroutine.send(value)
        coroutine.close()
