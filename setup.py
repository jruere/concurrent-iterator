# vim : fileencoding=UTF-8 :

from setuptools import setup

import concurrent_iterator


setup(
    name='concurrent-iterator',
    version=concurrent_iterator.__version__,
    description='Classes to run producers (iterators) and consumers'
                ' (coroutines) in a background thread/process.',
    url='https://github.com/jruere/concurrent-iterator',
    license="LGPLv3",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Operating System :: POSIX',
    ],
    keywords="concurrency parallelism iterator iterable",
    author="Javier Ruere",
    author_email="javier@ruere.com.ar",
    zip_safe=True,
    packages=['concurrent_iterator', 'concurrent_iterator.tests'],
    platforms=["POSIX"],
    test_suite="concurrent_iterator.tests",
    install_requires=['decorator'],
    tests_require=['mock'],
)
