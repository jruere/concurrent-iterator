# vim: set fileencoding=utf-8
from __future__ import absolute_import, division, unicode_literals

import time


class AbstractSpawnedIteratorTest(object):

    def _create_spawned_iterator(self, iterable):
        raise NotImplementedError

    def test_when_a_generator_is_spawned_then_it_generates_the_same_values(self):
        values = [1, 2, 3]

        subject = self._create_spawned_iterator(iter(values))

        results = list(subject)

        self.assertEqual(values, results)

    def test_when_generating_element_takes_time_then_it_should_be_faster_than_sequential(self):
        def gen(count, delay):
            for i in range(count):
                time.sleep(delay)
                yield i

        count = 3
        delay = 0.1

        subject = self._create_spawned_iterator(iter(gen(count, delay)))

        time.sleep(count * delay)  # Give background thread time to consume.

        t0 = time.time()
        results = list(subject)
        tf = time.time() - t0

        self.assertEqual(list(range(count)), results)
        self.assertAlmostEqual(0, tf, 1)
