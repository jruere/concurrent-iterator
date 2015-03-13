# concurrent-iterator

Iterators that consume and buffer generator values in a background
thread/process.


## Implementations

There are currently 3 implementations:

* DummySpawnedIterator: non-concurrent implementation
* ThreadSpawnedIterator: uses a background thread to run the generator
* ProcessSpawnedIterator: uses a background process to run the generator

DummySpawnedIterator is useless in practice.

ThreadSpawnedIterator is useful for IO bound generators.

ProcessSpawnedIterator is useful for CPU or IO bound generators.
It has the complications of dealing with processes (different memory spaces,
logging, etc).
For logging, module `multiprocessing-logging` can be used.


## Usage

Basic example:

    from concurrent_iterator.thread import SpawnedIterator
    
    ...
    
    items = SpawnedIterator(slow_generator, max_size=5)
    
    for item in items:
        [Do some time consuming task]

In the previous example, while doing some time consuming task, the
`slow_generator` will continue running in a background thread and will
pre-calculate up to 5 values.
