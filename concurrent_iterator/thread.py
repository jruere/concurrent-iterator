from __future__ import annotations

import logging
import threading
from collections.abc import Iterable, Iterator
from contextlib import suppress
from queue import Empty, Full, Queue
from typing import Any, Literal, TypeVar

from concurrent_iterator import (
    ConsumerCoroutine,
    IConsumer,
    IProducer,
    WillNotConsume,
)
from concurrent_iterator._internal import (
    ExceptionInUserIterable,
    StopIterationSentinel,
    check_open,
)

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

    This implementation is useful for IO-bound generators, or when the
    consuming code in the main thread is IO-bound.
    """

    def __init__(self, iterables: Iterable[Iterable[T_co]], maxsize: int = 100) -> None:
        assert maxsize > 0, f"`maxsize` must be positive, but is {maxsize}."

        self._queue: Queue[T_co | ExceptionInUserIterable | type[StopIterationSentinel]] = Queue(
            maxsize
        )
        self._threads: list[threading.Thread] = []
        self._closed = False
        self._stop_event = threading.Event()

        self._spawn_workers(iterables)
        self._active_threads = len(self._threads)

        if not self._active_threads:
            self.close()  # Got no iterables.

    def _spawn_workers(self, iterables: Iterable[Iterable[T_co]]) -> None:
        for iterable in iterables:
            thread = threading.Thread(
                target=self._run, args=(iter(iterable), self._queue, self._stop_event)
            )
            thread.start()

            self._threads.append(thread)

    def __next__(self) -> T_co:
        if self._closed:
            raise StopIteration

        while True:
            try:
                item = self._queue.get(timeout=0.1)
            except Empty:
                if self._closed or self._stop_event.is_set():
                    raise StopIteration
                continue

            if item is StopIterationSentinel:
                self._active_threads -= 1
                if not self._active_threads:
                    self.close()

                    raise StopIteration
            elif isinstance(item, ExceptionInUserIterable):
                # Any generator raising an exception terminates the entire
                # MultiProducer as generators don't continue after an exception.
                self.close()
                raise item.exception
            else:
                # Mypy does not narrow the type when comparing with `is`.
                return item  # type: ignore[return-value]

    def __iter__(self) -> Iterator[T_co]:
        return self

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        self._stop_event.set()

        for thread in self._threads:
            thread.join(timeout=1.0)
            if thread.is_alive():
                logging.getLogger(__name__ + "." + type(self).__name__).warning(
                    "Thread %s did not terminate", thread
                )

        self._active_threads = 0
        del self._queue

    def __enter__(self) -> MultiProducer[T_co]:
        return self

    def __exit__(self, *_: object) -> Literal[False]:
        self.close()
        return False

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            logging.getLogger(__name__ + "." + type(self).__name__).exception(
                "Exception in __del__"
            )

    @staticmethod
    def _run(iterator: Iterator[T_co], queue: Queue[Any], stop_event: threading.Event) -> None:
        try:
            while not stop_event.is_set():
                item = next(iterator)
                MultiProducer._put_cooperatively(queue, item, stop_event)
        except StopIteration:
            MultiProducer._put_cooperatively(queue, StopIterationSentinel, stop_event)
        except Exception as e:  # noqa: BLE001  # intentional: forward user iterable exception
            MultiProducer._put_cooperatively(queue, ExceptionInUserIterable(e), stop_event)

    @staticmethod
    def _put_cooperatively(queue: Queue[Any], item: Any, stop_event: threading.Event) -> bool:
        while not stop_event.is_set():
            with suppress(Full):
                queue.put(item, timeout=0.1)
                return True
        return False


class Producer(MultiProducer[T_co]):
    """Uses a thread to produce and buffer values from the given iterable.

    This implementation is useful for IO-bound generators, or when the
    consuming code in the main thread is IO-bound.
    """

    def __init__(self, iterable: Iterable[T_co], maxsize: int = 100) -> None:
        assert maxsize > 0, f"`maxsize` must be positive, but is {maxsize}."

        super().__init__([iterable], maxsize)


class Consumer(IConsumer[T_contra]):
    """Feeds the given coroutine in a separate thread."""

    def __init__(
        self,
        coroutine: ConsumerCoroutine[T_contra],
        maxsize: int = 1,
        close_timeout_secs: float = 10.0,
    ):
        assert maxsize > 0, f"`maxsize` must be positive, but is {maxsize}."
        assert (
            close_timeout_secs > 0
        ), f"`close_timeout_secs` must be positive, but is {close_timeout_secs}."

        self._coroutine = coroutine
        self._close_timeout_secs = close_timeout_secs

        self._closed = False
        self._error: BaseException | None = None
        self._queue: Queue[Any] = Queue(maxsize)
        self._thread = threading.Thread(target=self._run, args=(coroutine, self._queue))

        self._thread.start()

    @check_open
    def send(self, value: T_contra, timeout: float = 0) -> None:
        assert timeout >= 0, f"`timeout` must be non-negative, but is {timeout}."

        # Fail fast once the worker is known to have failed: close() releases
        # resources and re-raises the stashed error. No lock: the worker is
        # the only writer, a stale read merely delays this by one send, and
        # close() joins the worker before reading.
        if self._error is not None:
            self.close()
        try:
            self._queue.put(value, block=(timeout != 0), timeout=timeout)
        except Full:
            raise WillNotConsume()

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        # A dead worker needs no sentinel; don't block waiting for one that
        # will never drain the queue (e.g. after it failed).
        if self._thread.is_alive():
            # Try to enqueue sentinel without losing pending values; if queue full
            # and consumer is slow, drain one item to avoid indefinite hang.
            try:
                self._queue.put(StopIterationSentinel, timeout=self._close_timeout_secs)
            except Full:
                while True:
                    with suppress(Empty):
                        self._queue.get_nowait()
                    with suppress(Full):
                        self._queue.put(StopIterationSentinel, timeout=0.1)
                        break

        self._thread.join()
        del self._thread
        if not self._queue.empty():
            logging.getLogger(__name__ + "." + type(self).__name__).error(
                "Closed with %d messages in queue.", self._queue.qsize()
            )
        del self._queue

        if self._error is not None:
            raise self._error

    @property
    def closed(self) -> bool:
        return self._closed

    def __enter__(self) -> Consumer[T_contra]:
        return self

    def __exit__(self, *_: object) -> Literal[False]:
        self.close()
        return False

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            logging.getLogger(__name__ + "." + type(self).__name__).exception(
                "Exception in __del__"
            )

    def _run(self, coroutine: ConsumerCoroutine[T_contra], queue: Queue[Any]) -> None:
        try:
            for value in iter(queue.get, StopIterationSentinel):
                coroutine.send(value)
        except Exception as e:  # noqa: BLE001
            self._error = e
        finally:
            coroutine.close()
