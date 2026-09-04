# concurrent-iterator

[![Supported Python versions](https://img.shields.io/pypi/pyversions/concurrent-iterator.svg)](https://pypi.org/pypi/concurrent-iterator/)
[![License](https://img.shields.io/pypi/l/concurrent-iterator.svg)](https://pypi.org/pypi/concurrent-iterator/)

## Intro

Classes to run Producers (iterators) and Consumers (coroutines) introducing concurrency.

There are many libraries to create pipelines with stages running in separate processes, a nice
one is [parallelpipe](https://pypi.org/project/parallelpipe/), but this library does something
different. It runs the entire upstream iterable (the Producer) in a background thread or process,
while the downstream consumption code stays in the foreground. It's a more coarse library but
easier to integrate since things keep looking like normal generators.

## Installation

```
pip install concurrent-iterator
```

## Implementations

There are three modules, each providing a `Producer`, a `Consumer`, and (for `thread`) a
`MultiProducer`:

* `dummy`: non-concurrent implementation, useful for testing or as a drop-in
  replacement when concurrency is not needed.
* `thread`: uses a background thread to run the iterable or coroutine.
  Useful for IO-bound work.
* `process`: uses a background process to run the iterable or coroutine.
  Useful for CPU or IO-bound work. It has the complications of dealing with
  processes (different memory spaces, logging, etc).
  For logging, module [`multiprocessing-logging`](https://github.com/jruere/multiprocessing-logging) can be used.

All `Producer`, `MultiProducer`, and `Consumer` classes implement the `IProducer` and
`IConsumer` interfaces defined in `concurrent_iterator` (the package root). They support:

* **Iteration** (`__next__` / `__iter__`) — Producers yield values from the background iterable.
* **Sending** (`Consumer.send`) — Consumers forward values to the background coroutine.
* **Explicit close** (`close()`) — stops the background worker and releases resources.
* **State inspection** (`closed` property) — checks whether the worker has been closed.
* **Context manager** (`with` statement) — `close()` is called automatically on exit.

## Usage

### Producer

```python
import time
from concurrent_iterator.thread import Producer

def slow_generator(count):
    for i in range(count):
        time.sleep(0.5)  # Simulate a slow producer
        yield i

# Pre-calculate up to 5 values while the main thread consumes them.
with Producer(slow_generator(10), maxsize=5) as items:
    for item in items:
        print(item)  # Do some time-consuming task
```

In this example, while the main thread processes each `item`, `slow_generator`
continues running in a background thread and pre-calculates up to 5 values.
The `with` statement ensures the background thread is properly cleaned up.

### Consumer

```python
from concurrent_iterator.thread import Consumer

def worker():
    while True:
        value = yield  # Coroutine protocol
        # ... do work with value ...

coro = worker()
next(coro)  # Prime the coroutine

with Consumer(coro, maxsize=5) as consumer:
    consumer.send("a")
    consumer.send("b")
    # close() is called automatically on exit, which also closes the coroutine.
```

The Consumer runs the coroutine in a background thread. `send()` enqueues values;
if the value cannot be enqueued within `timeout` (default `0`, never blocks),
it raises `concurrent_iterator.WillNotConsume`, signaling the caller to retry.

### Context manager

Both Producers and Consumers can be used as context managers. When the `with`
block exits, `close()` is called automatically, ensuring background threads or
processes are terminated even on exceptions.

```python
from concurrent_iterator.thread import Producer

with Producer(range(100), maxsize=10) as items:
    for item in items:
        if item > 5:
            break  # close() is still called by the with block
```

## Exception handling

Exceptions raised by generators are forwarded to the main thread. When a
generator raises, the producer forwards the exception, re-raising it from
`__next__()`. After an exception, the producer is terminated and raises
`StopIteration` on subsequent calls.

For `process.Producer`, if the child process terminates unexpectedly,
`__next__()` raises `RuntimeError("Child process died.")`, and becomes closed.

## Limitations

> **Limitations:** `process.Producer`/`process.Consumer` with generators,
> coroutines and other unpicklable objects require the `fork` start method.
> Python 3.14 changes the default on Linux from `fork` to `forkserver`,
> and `spawn`/`forkserver` cannot pickle generators (`TypeError: cannot
> pickle 'generator' object`). In those cases `process.Producer`/`process.Consumer`
> raises `RuntimeError` with a clear message. Use `thread.Producer`/
> `thread.Consumer`, a picklable iterable (e.g. `iter([1,2,3])`), or pass
> `mp_context=multiprocessing.get_context('fork')` where `fork` is available
> (Linux).
