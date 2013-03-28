#!/usr/bin/env python

from __future__ import with_statement

from setuptools import setup


def get_version(fname='latexmake.py'):
    with open(fname) as f:
        for line in f:
            if line.startswith('__version__'):
                return eval(line.split('=')[-1])


def get_long_description():
    descr = []
    for fname in ('README.rst',):
        with open(fname) as f:
            descr.append(f.read())
    return '\n\n'.join(descr)


setup(
    name='latexmk.py',
    version=get_version(),
    description=('Latexmk.py completely automates the process of '
                 'generating a LaTeX document.'),
    long_description=get_long_description(),
    author='Marc Schlaich',
    author_email='marc.schlaich@googlemail.com',
    url='http://github.com/schlamar/latexmk.py',
    license='MIT',
    platforms='any',
    classifiers=['Development Status :: 4 - Beta',
                 'Intended Audience :: End Users/Desktop',
                 'License :: OSI Approved :: MIT License',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'Programming Language :: Python :: 2',
                 'Programming Language :: Python :: 3',
                 'Topic :: Printing',
                 'Topic :: Text Processing :: Markup :: LaTeX'],
    py_modules=['latexmake'],
    entry_points={'console_scripts': ['latexmk.py = latexmake:main']},
)
