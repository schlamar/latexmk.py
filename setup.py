from distutils.core import setup

from latexmk import __version__

setup(
      name = 'latexmk.py',      
      version = __version__, 
      scripts = ['latexmk.py']
      )
