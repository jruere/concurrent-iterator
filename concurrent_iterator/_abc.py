from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Literal, TypeVar

from concurrent_iterator import IConsumer, IProducer

T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


class BaseProducer(IProducer[T_co], ABC):
    """Shared lifecycle for producers; subclasses implement `__next__` and `_do_close`."""

    def __init__(self) -> None:
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def __iter__(self) -> Iterator[T_co]:
        return self

    def __enter__(self) -> BaseProducer[T_co]:
        return self

    def __exit__(self, *args: object) -> Literal[False]:
        self.close()
        return False

    def __del__(self) -> None:
        try:
            if not hasattr(self, "_closed"):
                return
            self.close()
        except Exception:
            logging.getLogger(type(self).__module__ + "." + type(self).__name__).exception(
                "Exception in __del__"
            )

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        self._do_close()

    @abstractmethod
    def _do_close(self) -> None:
        """Release resources; called once by `close()` after marking closed."""


class BaseConsumer(IConsumer[T_contra], ABC):
    """Shared lifecycle for consumers; subclasses implement `send` and `_do_close`."""

    def __init__(self) -> None:
        self._closed = False
        self._error: BaseException | None = None

    @property
    def closed(self) -> bool:
        return self._closed

    def __enter__(self) -> BaseConsumer[T_contra]:
        return self

    def __exit__(self, *args: object) -> Literal[False]:
        self.close()
        return False

    def __del__(self) -> None:
        try:
            if not hasattr(self, "_closed"):
                return
            self.close()
        except Exception:
            logging.getLogger(type(self).__module__ + "." + type(self).__name__).exception(
                "Exception in __del__"
            )

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        self._do_close()
        if self._error is not None:
            raise self._error

    @abstractmethod
    def _do_close(self) -> None:
        """Release resources; called once by `close()` after marking closed."""
