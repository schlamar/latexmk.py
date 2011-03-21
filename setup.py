#!/usr/bin/env python

from distribute_setup import use_setuptools
use_setuptools()

from setuptools import setup

        
setup(
      name = 'latexmk.py',      
      version = '0.2', 
      description=('Latexmk.py completely automates the process of '
                   'generating a LaTeX document.'),
      long_description=('Latexmk.py completely automates the process of '
                        'generating a LaTeX document. Given the source files '
                        'for a document, latexmk.py issues the appropriate '
                        'sequence of commands to generate a .dvi or .pdf '
                        'version of the document.'),
      author='Marc Schlaich',  
      author_email='marc.schlaich@googlemail.com',
      url='http://bitbucket.org/ms4py/latexmk.py/',
      license='MIT',
      platforms = 'any',
      classifiers=['Development Status :: 4 - Beta',
                   'Intended Audience :: End Users/Desktop',
                   'License :: OSI Approved :: MIT License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Topic :: Printing',
                   'Topic :: Text Processing :: Markup :: LaTeX'],
                   
      py_modules = ['latexmk'],
      entry_points = {'console_scripts': ['latexmk = latexmk:main']},
      use_2to3 = True
      )
