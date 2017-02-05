# vim: set fileencoding=utf-8

from collections import deque
from time import sleep

class RingQueue(object):
    """A simple wrapper around deque to mimic the Queue operations"""
    def __init__(self, maxsize):
        super(RingQueue, self).__init__()
        self._deque = deque(maxlen=maxsize)

    def put(self, item):
        self._deque.append(item)

    def get(self):
        while True:
            try:
                return self._deque.pop()
            except IndexError:
                sleep(1e-3)




