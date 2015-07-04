#!/usr/bin/env python
import os
from setuptools import setup, find_packages
from sarah import __name__ as PACKAGE_NAME
from sarah import VERSION

DESCRIPTION = "Handy Bot"
ROOT_DIR = os.path.dirname
SOURCE_DIR = os.path.join(ROOT_DIR)

try:
    import pypandoc

    long_description = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError, OSError, RuntimeError):
    try:
        long_description = open(os.path.join(
            os.path.dirname(__file__), 'README.md')).read()
    except:
        long_description = DESCRIPTION + '\n'

setup(
    name=PACKAGE_NAME,
    description=DESCRIPTION,
    long_description=long_description,
    author='Go Hagiwara a.k.a Oklahomer',
    author_email='hagiwara.go@gmail.com',
    url='https://github.com/oklahomer/sarah',
    version=VERSION,
    install_requires=open('requirements.txt').read().splitlines(),
    packages=find_packages(),
    include_package_data=True,
    classifiers=['Programming Language :: Python'],
)
