# vim : fileencoding=UTF-8 :

from setuptools import setup


setup(
    name='concurrent-iterator',
    version='0.2.6',
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
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Operating System :: POSIX',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords="concurrency parallelism iterator iterable pipeline",
    author="Javier Ruere",
    author_email="javier@ruere.com.ar",
    zip_safe=True,
    packages=['concurrent_iterator'],
    platforms=["POSIX"],
    test_suite="tests",
    install_requires=['decorator'],
    tests_require=['mock'],
)
