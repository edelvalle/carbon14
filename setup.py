# -*- coding: utf-8 -*-
import os
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


VERSION = '1.0.0rc14'

setup(
    name='carbon14',
    version=VERSION,
    description="Serializer library with GraphQL query support.",
    long_description=read('README.md'),
    classifiers=[
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Development Status :: 3 - Alpha',
        'Operating System :: OS Independent',
    ],
    keywords='',
    author='Eddy Ernesto del Valle Pino',
    author_email='eddy@edelvalle.me',
    packages=find_packages(exclude=("tests",)),
    install_requires=[],
    tests_require=[
        'pytest',
        'pytest-cov',
    ],
    include_package_data=True,
    zip_safe=True,
)
