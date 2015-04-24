# concurrent-iterator

[![Downloads](https://pypip.in/download/concurrent-iterator/badge.svg)](https://pypi.python.org/pypi/concurrent-iterator/)
[![Supported Python versions](https://pypip.in/py_versions/concurrent-iterator/badge.svg)](https://pypi.python.org/pypi/concurrent-iterator/)
[![Development Status](https://pypip.in/status/concurrent-iterator/badge.svg)](https://pypi.python.org/pypi/concurrent-iterator/)
[![Download format](https://pypip.in/format/concurrent-iterator/badge.svg)](https://pypi.python.org/pypi/concurrent-iterator/)
[![License](https://pypip.in/license/concurrent-iterator/badge.svg)](https://pypi.python.org/pypi/concurrent-iterator/)


Classes to run producers (iterators) and consumers (coroutines) in a background thread/process.


## Implementations

There are currently 3 implementations:

* `dummy.Producer`: non-concurrent implementation
* `thread.Producer`: uses a background thread to run the generator
* `process.Producer`: uses a background process to run the generator

`dummy.Producer` is useless in practice.

`thread.Producer` is useful for IO bound generators.

`process.Producer` is useful for CPU or IO bound generators.
It has the complications of dealing with processes (different memory spaces,
logging, etc).
For logging, module [`multiprocessing-logging`](https://github.com/jruere/multiprocessing-logging) can be used.


## Usage

Basic example:

    from concurrent_iterator.thread import Producer
    
    ...
    
    items = Producer(slow_generator, max_size=5)
    
    for item in items:
        [Do some time consuming task]

In the previous example, while doing some time consuming task, the
`slow_generator` will continue running in a background thread and will
pre-calculate up to 5 values.
