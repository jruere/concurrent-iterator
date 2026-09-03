# concurrent-iterator

[![Supported Python versions](https://img.shields.io/pypi/pyversions/concurrent-iterator.svg)](https://pypi.org/pypi/concurrent-iterator/)
[![License](https://img.shields.io/pypi/l/concurrent-iterator.svg)](https://pypi.org/pypi/concurrent-iterator/)

## Intro

Classes to run producers (iterators) and consumers (coroutines) in a background thread/process.

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

### `dummy` module

* `dummy.Producer(iterable, maxsize=None)` — non-concurrent. `maxsize` is accepted
  (must be positive or `None`) but ignored.
* `dummy.Consumer(coroutine)` — non-concurrent. The `timeout` parameter of `send()`
  is not supported and will raise `AssertionError` if non-zero.

### `thread` module

* `thread.MultiProducer(iterables, maxsize=100)` — runs multiple iterables in
  separate background threads, merging their values into a single output stream.
  The `maxsize` limit applies to the total output, not individual producers.
  Exceptions in any iterator terminate the entire `MultiProducer`.
* `thread.Producer(iterable, maxsize=100)` — convenience wrapper around
  `MultiProducer` for a single iterable.
* `thread.Consumer(coroutine, maxsize=1, close_timeout_secs=10.0)` — feeds a
  coroutine in a separate thread. `close_timeout_secs` controls how long
  `close()` waits for the queue to drain before forcibly moving on.

`maxsize` defaults to 100 for all thread producers and 1 for the consumer.

### `process` module

* `process.Producer(iterable, maxsize=100, chunksize=1)` — runs the iterable in
  a separate process. `chunksize` controls how many items are batched into each
  inter-process message (must be positive; `maxsize >= chunksize`).
* `process.Consumer(coroutine, maxsize=1, shutdown_timeout_secs=1.0)` — feeds a
  coroutine in a separate process. `shutdown_timeout_secs` controls how long
  `close()` waits for the child process to finish.

`maxsize` defaults to 100 for producers and 1 for consumers, matching the
thread implementations.

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
    received = []
    while True:
        value = yield  # Coroutine protocol
        received.append(value)
    # ... do work with value ...

coro = worker()
next(coro)  # Prime the coroutine

with Consumer(coro, maxsize=5) as consumer:
    consumer.send("a")
    consumer.send("b")
    # close() is called automatically on exit, which also closes the coroutine.
```

The Consumer runs the coroutine in a background thread. `send()` enqueues values;
if the queue is full and a `timeout` is given, it raises `WillNotConsume`
(imported from `concurrent_iterator`), signaling the caller to retry.

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
generator raises, the producer wraps the exception and re-raises it from
`__next__()`. After an exception, the producer is terminated and raises
`StopIteration` on subsequent calls.

For `process.Producer`, if the child process terminates unexpectedly,
`__next__()` raises `RuntimeError("Child process died.")` after draining any
buffered items.

## Limitations

> **Limitations:** `process.Producer`/`process.Consumer` with generators,
> coroutines and other unpicklable objects require the `fork` start method.
> Python 3.14 changes the default on Linux from `fork` to `forkserver`,
> and `spawn`/`forkserver` cannot pickle generators (`TypeError: cannot
> pickle 'generator' object`). In those cases `process.Producer`/`process.Consumer`
> now raise `RuntimeError` with a clear message. Use `thread.Producer`/
> `thread.Consumer`, a picklable iterable (e.g. `iter([1,2,3])`), or force
> `fork` via `multiprocessing.set_start_method('fork', force=True)` or
> `multiprocessing.get_context('fork').Process`/`Queue` where `fork` is
> available (Linux).
