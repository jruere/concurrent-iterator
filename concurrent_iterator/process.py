from __future__ import annotations

import itertools
import logging
import multiprocessing
import pickle
import time
from collections.abc import Iterable, Iterator
from contextlib import suppress
from multiprocessing.context import BaseContext
from queue import Empty, Full
from typing import Literal, TypeVar, Union

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

# 3.9 does not like "|" between TypeVar and type.
_QT = Union[list[Union[T_co, ExceptionInUserIterable]], type[StopIterationSentinel]]


def _resolve_mp_context(mp_context: BaseContext | None) -> BaseContext:
    if mp_context is None:
        return multiprocessing.get_context()
    return mp_context


class Producer(IProducer[T_co]):
    """Uses a separate process to produce and buffer values from the given
    iterable.

    This implementation is useful for CPU or IO bound generators, or when the
    consuming code in the main thread is CPU or IO bound.

    See multiprocessing.Pool for a more useful abstraction for CPU bound
    producers.

    For logging to work properly, use multiprocessing-logging.

    :param mp_context: multiprocessing context used for Queue and Process.
        Defaults to the global default context
        (`multiprocessing.get_context()`). Pass e.g.
        `multiprocessing.get_context("fork")` to use generators and other
        unpicklable iterables without touching global state.
    """

    def __init__(
        self,
        iterable: Iterable[T_co],
        maxsize: int = 100,
        chunksize: int = 1,
        mp_context: BaseContext | None = None,
    ) -> None:
        assert chunksize > 0, f"`chunksize` must be positive, but is {chunksize}."
        assert maxsize >= chunksize, f"`maxsize` ({maxsize}) must be >= `chunksize` ({chunksize})."

        self._iterator = iter(iterable)

        ctx = _resolve_mp_context(mp_context)
        self._queue: multiprocessing.Queue[_QT[T_co]] = ctx.Queue(maxsize // chunksize)
        self._closed = False
        self._current_chunk: list[T_co | ExceptionInUserIterable] = []
        self._log = logging.getLogger(__name__ + "." + type(self).__name__)
        # BaseContext stubs omit Process (only concrete contexts define it).
        self._process = ctx.Process(  # type: ignore[attr-defined]
            target=self._run,
            args=(self._iterator, self._queue, chunksize),
        )

        self._process.daemon = True
        self._log.info("Starting process.")
        try:
            self._process.start()
        except (TypeError, pickle.PicklingError) as e:
            if ctx.get_start_method() != "fork":
                raise RuntimeError(
                    "process.Producer with generators and other unpicklable "
                    "iterables requires start method 'fork', got "
                    f"'{ctx.get_start_method()}' (Python 3.14 defaults to 'forkserver'). Use "
                    "thread.Producer, a picklable iterable, or "
                    "mp_context=multiprocessing.get_context('fork')."
                ) from e
            raise

    def __next__(self) -> T_co:
        is_process_alive = True  # Cheap assumption.

        while not self._closed and not self._current_chunk:
            try:
                chunk = self._queue.get(timeout=0.1)
            except Empty:
                # To avoid a race condition, reporting this error condition is delayed one loop.
                if not is_process_alive:
                    raise RuntimeError("Child process died.")
                is_process_alive = self._process.is_alive()
            else:
                if chunk is StopIterationSentinel:
                    self.close()
                else:
                    assert isinstance(chunk, list), chunk  # For mypy and as sanity check.
                    # Reversed to consume it as a stack.
                    self._current_chunk.extend(reversed(chunk))

        if self._closed:
            raise StopIteration

        item = self._current_chunk.pop()

        if isinstance(item, ExceptionInUserIterable):
            self.close()
            raise item.exception

        return item

    def __iter__(self) -> Iterator[T_co]:
        return self

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        if self._process.is_alive():
            self._process.terminate()
        self._process.join(timeout=1.0)
        with suppress(Exception):
            self._queue.close()
            self._queue.cancel_join_thread()
        del self._queue
        del self._current_chunk

    def __enter__(self) -> Producer[T_co]:
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

    def _run(
        self, iterator: Iterator[T_co], queue: multiprocessing.Queue[_QT[T_co]], chunksize: int
    ) -> None:
        while True:
            chunk: list[T_co | ExceptionInUserIterable] = []
            # Items must be added one at a time to avoid losing items
            # before an exception.
            try:
                for item in itertools.islice(iterator, chunksize):
                    chunk.append(item)  # noqa: PERF402
            except Exception as e:  # noqa: BLE001  # intentional: forward user iterable exception.
                self._log.exception("Exception on iterator.")

                chunk.append(ExceptionInUserIterable(e))
                queue.put(chunk)
                queue.close()
                queue.join_thread()

                break  # Per PEP 255, this terminates the iterable.
            else:
                if not chunk:
                    queue.put(StopIterationSentinel)  # Signal we are done.
                    break
                else:
                    queue.put(chunk)


class Consumer(IConsumer[T_contra]):
    """Feeds the given coroutine in a separate process.

    :param mp_context: multiprocessing context used for Queue and Process.
        Defaults to the global default context
        (`multiprocessing.get_context()`). Pass e.g.
        `multiprocessing.get_context("fork")` for unpicklable coroutines
        without touching global state.
    """

    def __init__(
        self,
        coroutine: ConsumerCoroutine[T_contra],
        maxsize: int = 1,
        shutdown_timeout_secs: float = 1.0,
        mp_context: BaseContext | None = None,
    ) -> None:
        assert maxsize > 0, f"`maxsize` must be positive, but is {maxsize}."
        assert (
            shutdown_timeout_secs > 0
        ), f"`shutdown_timeout_secs` must be positive, but is {shutdown_timeout_secs}."

        ctx = _resolve_mp_context(mp_context)
        self._coroutine: ConsumerCoroutine[T_contra] = coroutine
        self._shutdown_timeout_secs = shutdown_timeout_secs

        self._closed = False
        self._error: BaseException | None = None
        self._queue: multiprocessing.Queue[T_contra | type[StopIterationSentinel]] = ctx.Queue(
            maxsize
        )
        self._errors: multiprocessing.Queue[BaseException] = ctx.Queue()
        # BaseContext stubs omit Process (only concrete contexts define it).
        self._process = ctx.Process(  # type: ignore[attr-defined]
            target=self._run, args=(coroutine, self._queue, self._errors)
        )

        self._process.daemon = True
        try:
            self._process.start()
        except (TypeError, pickle.PicklingError) as e:
            if ctx.get_start_method() != "fork":
                raise RuntimeError(
                    "process.Consumer with unpicklable coroutines requires "
                    f"start method 'fork', got '{ctx.get_start_method()}' (Python 3.14 defaults to "
                    "'forkserver'). Use thread.Consumer or "
                    "mp_context=multiprocessing.get_context('fork')."
                ) from e
            raise

    @check_open
    def send(self, value: T_contra, timeout: float = 0) -> None:
        # Fail fast once the worker is known to have failed: close() releases
        # resources and re-raises the stashed error.
        with suppress(Empty):
            self._error = self._errors.get_nowait()
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

        deadline = time.monotonic() + self._shutdown_timeout_secs
        try:
            self._queue.put(StopIterationSentinel, timeout=self._shutdown_timeout_secs)
        except Full:
            logging.getLogger(__name__ + "." + type(self).__name__).error(
                "Failed to put stop-iteration sentinel."
            )
        else:
            self._process.join(timeout=max(0.1, deadline - time.monotonic()))

        if self._process.is_alive():
            with suppress(Exception):
                self._process.terminate()
        self._process.join(timeout=1.0)
        del self._process

        self._queue.close()
        self._queue.cancel_join_thread()
        del self._queue

        if self._error is None:
            with suppress(Empty):
                self._error = self._errors.get_nowait()
        self._errors.close()
        self._errors.cancel_join_thread()
        del self._errors

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

    @staticmethod
    def _run(
        coroutine: ConsumerCoroutine[T_contra],
        queue: multiprocessing.Queue[T_contra | type[StopIterationSentinel]],
        errors: multiprocessing.Queue[BaseException],
    ) -> None:
        try:
            for value in iter(queue.get, StopIterationSentinel):
                # iter() strips the sentinel, but mypy cannot infer that.
                coroutine.send(value)  # type: ignore[arg-type]
        except Exception as e:  # noqa: BLE001
            errors.put(e)
        finally:
            coroutine.close()
