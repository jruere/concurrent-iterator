from functools import wraps


def check_open(f):
    @wraps(f)
    def _f(self, *args, **kwargs):
        if self.closed:
            raise ValueError(f"{f.__name__} operation on closed Consumer")
        return f(self, *args, **kwargs)

    return _f
