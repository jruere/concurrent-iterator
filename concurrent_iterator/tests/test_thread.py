# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals, print_function

import logging
import unittest

from concurrent_iterator.thread import SpawnedIterator
from tests import AbstractSpawnedIteratorTest

logging.basicConfig(level=logging.WARNING)


class ThreadSpawnedIteratorTest(unittest.TestCase, AbstractSpawnedIteratorTest):

    def _create_spawned_iterator(self, iterable):
        return SpawnedIterator(iterable)
