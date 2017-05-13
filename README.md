# concurrent-iterator

[![Run Status](https://api.shippable.com/projects/57c8a38983e2680f00fe6dc4/badge?branch=master)](https://app.shippable.com/projects/57c8a38983e2680f00fe6dc4)
[![Coverage Badge](https://api.shippable.com/projects/57c8a38983e2680f00fe6dc4/coverageBadge?branch=master)](https://app.shippable.com/projects/57c8a38983e2680f00fe6dc4)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/concurrent-iterator.svg)](https://pypi.python.org/pypi/multiprocessing-logging/)
[![License](https://img.shields.io/pypi/l/concurrent-iterator.svg)](https://pypi.python.org/pypi/multiprocessing-logging/)

## Intro

Classes to run producers (iterators) and consumers (coroutines) in a background thread/process.

There are many libraries to create pipelines with stages running in separate processes, a nice
one is [parallelpipe](https://pypi.python.org/pypi/parallelpipe), but this library does something
different. It will lift the entire pipeline up to the point of the Producer into a separate process 
or thread. It's a more coarse library but easier to integrate since things keep looking as normal generators.

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
    
    items = Producer(slow_generator, maxsize=5)
    
    for item in items:
        [Do some time consuming task]

In the previous example, while doing some time consuming task, the
`slow_generator` will continue running in a background thread and will
pre-calculate up to 5 values.
