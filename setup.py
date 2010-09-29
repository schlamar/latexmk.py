#!/usr/bin/python

from distutils.core import setup

import latexmk

setup(
      name = 'latexmk.py',      
      version = latexmk.__version__, 
      description=('Latexmk.py completely automates the process of '
                   'generating a LaTeX document.'),
      long_description=('Latexmk.py completely automates the process of '
                        'generating a LaTeX document. Given the source files '
                        'for a document, latexmk.py issues the appropriate '
                        'sequence of commands to generate a .dvi or .pdf '
                        'version of the document.'),
      author=latexmk.__author__,  
      author_email='marc.schlaich@googlemail.com',
      url='http://bitbucket.org/ms4py/latexmk.py/',
      license=latexmk.__license__,
      platforms = 'any',
      classifiers=['Development Status :: 4 - Beta',
                   'Intended Audience :: End Users/Desktop',
                   'License :: OSI Approved :: MIT License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Topic :: Printing',
                   'Topic :: Text Processing :: Markup :: LaTeX'],
      scripts = ['latexmk.py']
      )
