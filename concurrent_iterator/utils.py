# vim: set fileencoding=utf-8
from decorator import decorator


@decorator
def check_open(f, self, *args, **kwargs):
    if self.closed:
        raise ValueError("%s operation on closed Consumer" % f.__name__)
    return f(self, *args, **kwargs)
