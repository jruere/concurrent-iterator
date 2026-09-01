from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

R = TypeVar("R")


def check_open(func: Callable[..., R]) -> Callable[..., R]:
    @wraps(func)
    def _f(self: Any, *args: Any, **kwargs: Any) -> R:
        if self.closed:
            raise ValueError(f"{func.__name__} operation on closed Consumer")
        return func(self, *args, **kwargs)

    return cast(Callable[..., R], _f)
