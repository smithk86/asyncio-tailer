#!/usr/bin/env python

import os.path

from setuptools import setup


dir_ = os.path.abspath(os.path.dirname(__file__))
# get the version to include in setup()
with open(f'{dir_}/asynctailer/__init__.py') as fh:
    for line in fh:
        if '__VERSION__' in line:
            exec(line)


setup(
    name='asynctailer',
    version=__VERSION__,
    license='MIT',
    author='Kyle Smith',
    author_email='smithk86@gmail.com',
    url='https://github.com/smithk86/asynctailer',
    packages=[
        'asynctailer'
    ],
    install_requires=[
        'tailer',
        'janus'
    ]
)
