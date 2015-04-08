# vim: set fileencoding=utf-8
from abc import abstractmethod
from abc import ABCMeta
from collections import Iterator

__version__ = '0.1'


class IProducer(Iterator):
    """Interface for SpawnedIterators."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def __next__(self):
        pass


# Legacy name.
ISpawnedIterator = IProducer
