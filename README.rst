latexmk.py
==========

Overview
--------

Latexmk.py completely automates the process of generating
a LaTeX document. Given the source files for a document,
latexmk.py issues the appropriate sequence of commands to
generate a .dvi or .pdf version of the document.

Inspired by http://ctan.tug.org/tex-archive/support/latexmk/


Installation
------------

Preferable via pip::

    pip install latexmk.py

For source installation you need
`distribute <http://pypi.python.org/pypi/distribute>`_ or
`setuptools <http://pypi.python.org/pypi/setuptools>`_


Usage
-----

::

    $ latexmk.py [options] [filename]

For details run::

    $ latexmk.py -h


License
-------

MIT, see LICENSE for more details.
