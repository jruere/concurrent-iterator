# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals, print_function

import logging
import unittest

from concurrent_iterator.thread import Producer
from concurrent_iterator.tests import AbstractProducerTest

logging.basicConfig(level=logging.WARNING)


class ThreadProducerTest(unittest.TestCase, AbstractProducerTest):

    def _create_producer(self, iterable):
        return Producer(iterable)
