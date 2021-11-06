#!/usr/bin/env python

import os.path

from setuptools import setup  # type: ignore


dir_ = os.path.abspath(os.path.dirname(__file__))
# get the version to include in setup()
with open(f'{dir_}/asyncio_tailer/__init__.py') as fh:
    for line in fh:
        if '__VERSION__' in line:
            exec(line)


setup(
    name='asyncio-tailer',
    version=__VERSION__,  # type: ignore
    author='Kyle Smith',
    author_email='smithk86@gmail.com',
    description='Asyncio wrapper for pytailer (https://github.com/six8/pytailer)',
    url='https://github.com/smithk86/asyncio-tailer',
    packages=['asyncio_tailer'],
    license='MIT',
    install_requires=[
        'tailer',
        'janus'
    ],
    python_requires='>=3.7',
    classifiers=(
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
        "Framework :: AsyncIO",
    )
)
