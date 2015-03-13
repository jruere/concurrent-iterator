# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals
from concurrent_iterator import ISpawnedIterator


class SpawnedIterator(ISpawnedIterator):
    """Dummy implementation that doesn't use concurrency."""

    def __init__(self, iterable):
        self._iterator = iter(iterable)

    def __next__(self):
        return next(self._iterator)

    def next(self):
        return self.__next__()

