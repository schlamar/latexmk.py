#!/usr/bin/python
# coding: utf-8

'''
Latexmk.py completely automates the process of generating 
a LaTeX document. Given the source files for a document, 
latexmk.py issues the appropriate sequence of commands to 
generate a .dvi or .pdf version of the document. 
It is specialized to run as a custom builder for the 
Eclipse-Plugin "Texlipse".

See Website for details:
http://bitbucket.org/ms4py/latexmk.py/


Inspired by http://ctan.tug.org/tex-archive/support/latexmk/

#############################################################################

Licence (MIT)
-------------
 
Copyright (c) 2010, Marc Schlaich.
 
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
 
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
 
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''

from __future__ import with_statement

from collections import defaultdict
from contextlib import nested
from itertools import chain
from optparse import OptionParser, TitledHelpFormatter
from subprocess import Popen, PIPE

import os
import re
import shutil
import sys
import time

__author__ = 'Marc Schlaich'
__version__ = '0.2'
__license__ = 'MIT'



CITE_PATTERN = re.compile(r'\\citation\{(.*)\}')
ERROR_PATTTERN = re.compile(r'(?:^! (.*\nl\..*)$)|(?:^! (.*)$)|'
                            '(No pages of output.)', re.M)
LATEX_RERUN_PATTERNS = [re.compile(pattr) for pattr in 
                        [r'LaTeX Warning: Reference .* undefined',
                         r'LaTeX Warning: There were undefined references\.', 
                         r'LaTeX Warning: Label\(s\) may have changed\.',
                         r'No file .*(\.toc|\.lof)\.']]
TEXLIPSE_MAIN_PATTERN = re.compile(r'^mainTexFile=(.*)(?:\.tex)$', re.M)

LATEX_FLAGS = ['-interaction=nonstopmode', '-shell-escape']
MAX_RUNS = 5
NO_LATEX_ERROR = (
    'Could not run command "%s". '
    'Is your latex distribution under your PATH?'
)

class LatexMaker(object):
    '''
    Main class for generation process.
    '''
    def __init__(self, project_name, opt):
        self.opt = opt
        
        if project_name == '.texlipse':
            self.project_name = self._parse_texlipse_config()
        else:
            self.project_name = project_name
        
        if self.opt.pdf:
            self.latex_cmd = 'pdflatex'
        else:
            self.latex_cmd = 'latex'
        
        self.out = ''
        self.glossaries = dict()
        self.latex_run_counter = 0
        
        cite_counter, toc_file, gloss_files = self._read_latex_files()
                    
        self.latex_run()
        self.read_glossaries()
        
        gloss_changed = self.makeindex_runs(gloss_files)
        if gloss_changed or self._is_toc_changed(toc_file):
            self.latex_run()
  
        if self._need_bib_run(cite_counter):
            self.bibtex_run()
            self.latex_run()
                             
        while (self.latex_run_counter < MAX_RUNS):
            if not self.need_latex_rerun():
                break
            self.latex_run()
        
        if self.opt.preview:
            self.open_preview()
            
    def _parse_texlipse_config(self):
        '''
        Read the project name from the texlipse
        config file ".texlipse".
        '''
        # If Eclipse's workspace refresh, the 
        # ".texlipse"-File will be newly created,
        # so try again after short sleep if 
        # the file is still missing.
        if not os.path.isfile('.texlipse'):
            time.sleep(0.1)
            if not os.path.isfile('.texlipse'):
                print >> sys.stderr, \
                    '! Fatal error: File .texlipse is missing.'
                print >> sys.stderr, '! Exiting...'
                sys.exit(1)
        
        with open('.texlipse') as fobj:
            content = fobj.read()
        match = TEXLIPSE_MAIN_PATTERN.search(content)
        if match:
            project_name = match.groups()[0]
            if self.opt.verbose:
                print ('Found inputfile in ".texlipse": %s.tex' 
                       % project_name)
            return project_name
        else:
            print >> sys.stderr, '! Fatal error: Parsing .texlipse failed.'
            print >> sys.stderr, '! Exiting...'
            sys.exit(1)
            
    def _read_latex_files(self):
        '''
        Check if some latex output files exist
        before first latex run, process them and return 
        the generated data.
        
            - Parsing *.aux for citations counter and 
              existing glossaries.
            - Getting content of files to detect changes.
                - *.toc file
                - all available glossaries files
        '''
        if os.path.isfile('%s.aux' % self.project_name):
            cite_counter = self.generate_citation_counter()
            self.read_glossaries()
        else:
            cite_counter = {'%s.aux' % self.project_name: 
                            defaultdict(int)}
        
        fname = '%s.toc' % self.project_name
        if os.path.isfile(fname):
            with open(fname) as fobj:
                toc_file = fobj.read()
        else:
            toc_file = ''
        
        gloss_files = dict()      
        for gloss in self.glossaries:
            ext = self.glossaries[gloss][1]
            filename = '%s.%s' % (self.project_name, ext)
            if os.path.isfile(filename):
                with open(filename) as fobj:
                    gloss_files[gloss] = fobj.read()
                    
        return cite_counter, toc_file, gloss_files

            
    def _is_toc_changed(self, toc_file):
        '''
        Test if the *.toc file has changed during
        the first latex run.
        '''
        fname = '%s.toc' % self.project_name
        if os.path.isfile(fname):
            with open(fname) as fobj:
                if fobj.read() != toc_file:
                    return True
                    
    def _need_bib_run(self, old_cite_counter):
        '''
        Determine if you need to run "bibtex".
        1. Check if *.bib exists.
        2. Check latex output for hints.
        3. Test if the numbers of citations changed
           during first latex run.
        4. Examine *.bib for changes.
        '''
        if not os.path.isfile('%s.bib' % self.project_name):
            return False
        
        if (re.search('No file %s.bbl.' % self.project_name, self.out) or
            re.search('LaTeX Warning: Citation .* undefined', self.out)):
            return True
        
        if old_cite_counter != self.generate_citation_counter():
            return True
        
        if os.path.isfile('%s.bib.old' % self.project_name):
            new = '%s.bib' % self.project_name
            old = '%s.bib.old' % self.project_name
            with nested(open(new), open(old)) as (f_new, f_old):
                if f_new.read() != f_old.read():
                    return True
    
    def read_glossaries(self):
        '''
        Read all existing glossaries in the main aux-file.
        '''
        filename = '%s.aux' % self.project_name
        with open(filename) as fobj:
            main_aux = fobj.read()
            
        pattern = r'\\@newglossary\{(.*)\}\{.*\}\{(.*)\}\{(.*)\}' 
        for match in re.finditer(pattern, main_aux):
            name, ext_i, ext_o = match.groups()
            self.glossaries[name] = (ext_i, ext_o)
    
    def check_errors(self):
        '''
        Check if errors occured during a latex run by
        scanning the output.
        '''
        errors = ERROR_PATTTERN.findall(self.out)
        # "errors" is a list of tuples
        if errors:
            print >> sys.stderr, '! Errors occurred:'
            
            # pylint: disable-msg=W0142
            # With reference doc for itertools.chain there 
            # is no magic at all.
            # Removing carriage return "\r" because it is 
            # a new line in Eclipse console.
            print >> sys.stderr, '\n'.join(
                [error.replace('\r', '').strip() for error
                in chain(*errors) if error.strip()]
            )
            # pylint: enable-msg=W0142
            
            print >> sys.stderr, ('! See "%s.log" for details.'
                                  % self.project_name)
            if self.opt.exit_on_error:
                print >> sys.stderr, '! Exiting...'
                sys.exit(1)
               

    def generate_citation_counter(self):
        '''
        Generate dictionary with the number of citations in all
        included files. If this changes after the first latex run,
        you have to run "bibtex".
        '''
        cite_counter = dict()
        filename = '%s.aux' % self.project_name
        with open(filename) as fobj:
            main_aux = fobj.read()
        cite_counter[filename] = _count_citations(filename)
        
        for match in re.finditer(r'\\@input\{(.*.aux)\}', main_aux):
            filename = match.groups()[0]
            try:
                counter = _count_citations(filename)
            except IOError:
                pass
            else:
                cite_counter[filename] = counter
        
        return cite_counter
    
    def latex_run(self):
        '''
        Start latex run.
        '''
        if self.opt.verbose:
            print 'Running %s...' % self.latex_cmd
        cmd = [self.latex_cmd]
        cmd.extend(LATEX_FLAGS)
        cmd.append('%s.tex' % self.project_name)
        try:
            self.out = Popen(cmd, stdout=PIPE).communicate()[0]
        except OSError:
            print >> sys.stderr, NO_LATEX_ERROR % self.latex_cmd
        self.latex_run_counter += 1
        self.check_errors()
        
    def bibtex_run(self):
        '''
        Start bibtex run.
        '''
        if self.opt.verbose:
            print 'Running bibtex...'
        try:
            Popen(['bibtex', '%s' % self.project_name], stdout=PIPE).wait()
        except OSError:
            print >> sys.stderr, NO_LATEX_ERROR % 'bibtex'
            sys.exit(1)
        
        shutil.copy('%s.bib' % self.project_name, 
                    '%s.bib.old' % self.project_name)
        
    def makeindex_runs(self, gloss_files):
        '''
        Check for each glossary if it has to be regenerated 
        with "makeindex".
        
        @return: True if "makeindex" was called.
        '''
        gloss_changed = False
        for gloss in self.glossaries:
            make_gloss = False
            ext_i, ext_o = self.glossaries[gloss]
            fname_in = '%s.%s' % (self.project_name, ext_i)
            fname_out = '%s.%s' % (self.project_name, ext_o)
            if re.search('No file %s.' % fname_in, self.out):
                make_gloss = True
            else:
                with open(fname_out) as fobj:
                    try:
                        if gloss_files[gloss] != fobj.read():
                            make_gloss = True
                    except KeyError:
                        make_gloss = True
                        
            if make_gloss:
                if self.opt.verbose:
                    print 'Running makeindex (%s)...' % gloss
                try:
                    Popen(['makeindex', '-q',  '-s', 
                           '%s.ist' % self.project_name, 
                           '-o', fname_in, fname_out], 
                           stdout=PIPE).wait()
                except OSError:
                    print >> sys.stderr, NO_LATEX_ERROR % 'makeindex'
                    sys.exit(1)
                gloss_changed = True
                
        return gloss_changed
    
    def open_preview(self):
        '''
        Try to open a preview of the generated document.
        Currently only supported on Windows.
        '''
        if self.opt.verbose:
            print 'Opening preview...'
        if self.opt.pdf:
            ext = 'pdf'
        else:
            ext = 'dvi'
        try:                              
            os.startfile('%s.%s' % (self.project_name, ext))
        except AttributeError:
            print >> sys.stderr, (
                'Preview-Error: Preview function is currently only '
                'supported on Windows.'
            )
        except WindowsError:
            print >> sys.stderr, (
                'Preview-Error: Extension .%s is not linked to a '
                'specific application!' % ext
            )
                   
    def need_latex_rerun(self):
        '''
        Test for all rerun patterns if they match the output.
        '''
        for pattern in LATEX_RERUN_PATTERNS:
            if pattern.search(self.out):
                return True
        return False

class CustomFormatter(TitledHelpFormatter):
    '''
    Standard Formatter removes linkbreaks.
    '''
    def __init__(self):
        TitledHelpFormatter.__init__(self)
    def format_description(self, description):
        '''
        Description is manual formatted, no changes are done.
        '''
        return description
    
def _count_citations(aux_file):
    '''
    Counts the citations in an aux-file.
    
    @return: defaultdict(int) - {citation_name: number, ...}
    '''
    counter = defaultdict(int)
    with open(aux_file) as fobj:
        content = fobj.read()

    for match in CITE_PATTERN.finditer(content):
        name = match.groups()[0]
        counter[name] += 1
    
    return counter
    
def main():
    '''
    Set up "optparse" and pass the options to 
    a new instance of L{LatexMaker}.
    '''
    version = '%%prog %s' % __version__
    usage = 'Usage: %prog [options] filename'
    
    # Read description from doc
    doc_text = ''
    for line in __doc__.splitlines():
        if line.find('#') == 0:
            break
        doc_text += '  %s\n' % line    
    
    description = ('Description\n'
                   '===========\n'
                   '%s'
                   'Arguments\n'
                   '=========\n'
                   '  filename     input filename without extension (*.tex)\n'
                   % doc_text)
            
    parser = OptionParser(usage=usage, version=version, 
                          description=description, 
                          formatter=CustomFormatter())
    parser.add_option('-q', '--quiet',
                      action='store_false', dest='verbose', default=True,
                      help='don\'t print status messages to stdout')
    parser.add_option('-n', '--no-exit',
                      action='store_false', dest='exit_on_error', default=True,
                      help='don\'t exit if error occurs')
    parser.add_option('-p', '--preview',
                      action='store_true', dest='preview', default=False,
                      help='try to open preview of generated document')
    parser.add_option('--pdf', action='store_true', dest='pdf', 
                      default=False, help='use "pdflatex" instead of latex')
    
    opt, args = parser.parse_args()
    if len(args) != 1:
        parser.error('incorrect number of arguments')

    LatexMaker(args[0], opt)
    
if __name__ == '__main__':
    main()