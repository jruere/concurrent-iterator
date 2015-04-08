# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals, print_function

import logging
import unittest

from concurrent_iterator.process import Producer
from concurrent_iterator.tests import AbstractProducerTest

logging.basicConfig(level=logging.DEBUG)


class ProcessProducerTest(unittest.TestCase, AbstractProducerTest):

    def _create_producer(self, iterable):
        return Producer(iterable)
