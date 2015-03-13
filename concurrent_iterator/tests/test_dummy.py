# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals, print_function

import logging
import unittest

from concurrent_iterator.dummy import SpawnedIterator
from tests import AbstractSpawnedIteratorTest

logging.basicConfig(level=logging.WARNING)


class DummySpawnedIteratorTest(unittest.TestCase, AbstractSpawnedIteratorTest):

    def _create_spawned_iterator(self, iterable):
        return SpawnedIterator(iterable)

    def test_when_generating_element_takes_time_then_it_should_be_faster_than_sequential(self):
        pass  # Disabled since the dummy implementation is not concurrent.
