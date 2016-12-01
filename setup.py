# -*- coding: utf-8 -*-
import os
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


VERSION = '0.1.0'

setup(
    name='carbon14',
    version=VERSION,
    description="GraphQL extension for Serpy",
    long_description=read('README.md'),
    classifiers=[
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Programming Language :: Python :: 3.5',
        'Development Status :: 5 - Production/Stable',
        'Operating System :: OS Independent',
    ],
    keywords='',
    author='Eddy Ernesto del Valle Pino',
    author_email='eddy.delvalle@gmail.com',
    packages=find_packages(exclude=("tests",)),
    install_requires=[
        'serpy>=0.1.1,<0.2',
        'xoutil>=1.7.1,<1.8',
    ],
    include_package_data=True,
    zip_safe=True,
)
