from functools import wraps

def check_open(f):
    @wraps(f)
    def _f(self, *args, **kwargs):
        if self.closed:
            raise ValueError("%s operation on closed Consumer" % f.__name__)
        return f(self, *args, **kwargs)
    return _f
