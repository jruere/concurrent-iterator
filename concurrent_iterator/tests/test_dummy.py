# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals

import logging
import unittest

from concurrent_iterator.dummy import Producer
from concurrent_iterator.tests import AbstractProducerTest

logging.basicConfig(level=logging.WARNING)


class DummyProducerTest(unittest.TestCase, AbstractProducerTest):

    def _create_producer(self, iterable):
        return Producer(iterable)

    def test_when_generating_element_takes_time_then_it_should_be_faster_than_sequential(self):
        pass  # Disabled since the dummy implementation is not concurrent.
