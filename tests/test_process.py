# vim: set fileencoding=utf-8
import logging
import unittest

from concurrent_iterator.process import Producer
from tests import AbstractProducerTest


logging.basicConfig(level=logging.DEBUG)


class ProcessProducerTest(unittest.TestCase, AbstractProducerTest):

    def _create_producer(self, iterable):
        return Producer(iterable)
