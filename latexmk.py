#!/usr/bin/python
# coding: utf-8

'''
Latexmk.py completely automates the process of generating 
a LaTeX document. Given the source files for a document, 
latexmk.py issues the appropriate sequence of commands to 
generate a .dvi or .pdf version of the document.


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

__author__ = 'Marc Schlaich'
__version__ = '0.1'
__license__ = 'MIT'

from subprocess import Popen, PIPE
import re
import os
import sys
from collections import defaultdict
from contextlib import nested
import shutil
from itertools import chain
from optparse import OptionParser, TitledHelpFormatter


CITE_PATTERN = re.compile(r'\\citation\{(.*)\}')
ERROR_PATTTERN = re.compile(r'(?:^! (.*\nl\..*)$)|(?:^! (.*)$)', re.M)
LATEX_RERUN_PATTERNS = [re.compile(pattern) for pattern in 
                        [r'LaTeX Warning: Reference .* undefined',
                         r'LaTeX Warning: There were undefined references\.', 
                         r'LaTeX Warning: Label\(s\) may have changed\.']]

LATEX_FLAGS = ['-interaction=nonstopmode', '-shell-escape']
MAX_RUNS = 5

class LatexMaker(object):
    '''
    Main class for generation process.
    '''
    def __init__(self, project_name, opt):
        self.project_name = project_name
        self.opt = opt
        
        if self.opt.pdf:
            self.latex_cmd = 'pdflatex'
        else:
            self.latex_cmd = 'latex'
        
        self.out = ''
        self.glossaries = dict()
        self.gloss_files = defaultdict(str)
        
        if os.path.isfile('%s.aux' % self.project_name):
            cite_counter = self.generate_citation_counter()
            self.read_glossaries()
        else:
            cite_counter = {'%s.aux' % self.project_name: 
                            defaultdict(int)}
              
        for gloss in self.glossaries:
            ext = self.glossaries[gloss][1]
            filename = '%s.%s' % (self.project_name, ext)
            if os.path.isfile(filename):
                with open(filename) as fobj:
                    self.gloss_files[gloss] = fobj.read()
                    
        self.latex_run()
        latex_runs = 1
        self.read_glossaries()
            
        if self.makeindex_runs():
            self.latex_run()
            latex_runs += 1
                             
        make_bib = False
        if (re.search('No file %s.bbl.' % self.project_name, self.out) or
            re.search('LaTeX Warning: Citation .* undefined', self.out) or
            cite_counter != self.generate_citation_counter()):
            make_bib = True
        elif os.path.isfile('%s.bib.old' % self.project_name):
            with nested(open('%s.bib' % self.project_name), 
                        open('%s.bib.old' % self.project_name)) as (f_new, 
                                                                    f_old):
                if f_new.read() != f_old.read():
                    make_bib = True
            
        if make_bib and os.path.isfile('%s.bib' % self.project_name):
            self.bibtex_run()
            self.latex_run()
            latex_runs += 1
                             
        for _ in range(MAX_RUNS - latex_runs):
            if not self.need_latex_rerun():
                break
            self.latex_run()
            
        self.write_log()
        
        if self.opt.preview:
            self.open_preview()
    
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
        if errors:
            print
            print '! Errors occurred:'
            print '\n'.join(chain.from_iterable(
                              errorlines.splitlines() for errorlines
                              in chain.from_iterable(errors) if errorlines))
            print '! See "latexmk.log" for details.'
            self.write_log()
            if self.opt.exit_on_error:
                print '! Exiting...'
                sys.exit(1)
                
    def write_log(self):
        '''
        Write the output from the last latex run into
        a log file.
        '''
        with open('latexmk.log', 'w') as fobj:
            fobj.writelines('%s\n' % line for line in self.out.splitlines())
    
    def read_citations(self, aux_file):
        '''
        Counts the citations in an aux-file.
        '''
        counter = defaultdict(int)
        try:
            with open(aux_file) as fobj:
                content = fobj.read()
        except IOError:
            return -1
        
        for match in CITE_PATTERN.finditer(content):
            name = match.groups()[0]
            counter[name] += 1
        
        return counter
    
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
        cite_counter[filename] = self.read_citations(filename)
        
        for match in re.finditer(r'\\@input\{(.*.aux)\}', main_aux):
            filename = match.groups()[0]
            counter = self.read_citations(filename)
            if counter >= 0:
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
        self.out, _ = Popen(cmd, stdout=PIPE).communicate()
        self.check_errors()
        
    def bibtex_run(self):
        '''
        Start bibtex run.
        '''
        if self.opt.verbose:
            print 'Running bibtex...'
        Popen(['bibtex', '%s' % self.project_name], stdout=PIPE).wait()
        
        shutil.copy('%s.bib' % self.project_name, 
                    '%s.bib.old' % self.project_name)
        
    def makeindex_runs(self):
        '''
        Check for each glossary if it has to be regenerated 
        with "makeindex".
        '''
        rerun_latex = False
        for gloss in self.glossaries:
            make_gloss = False
            ext_i, ext_o = self.glossaries[gloss]
            fname_in = '%s.%s' % (self.project_name, ext_i)
            fname_out = '%s.%s' % (self.project_name, ext_o)
            if re.search('No file %s.' % fname_in, self.out):
                make_gloss = True
            else:
                with open(fname_out) as fobj:
                    if self.gloss_files[gloss] != fobj.read():
                        make_gloss = True
                        
            if make_gloss:
                if self.opt.verbose:
                    print 'Running makeindex (%s)...' % gloss
                Popen(['makeindex', '-q',  '-s', '%s.ist' % self.project_name, 
                       '-o', fname_in, fname_out], stdout=PIPE).wait()
                rerun_latex = True
                
        return rerun_latex
    
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
            print ('Preview-Error: Preview function is currently only '
                   'supported on Windows.')
        except WindowsError:
            print ('Preview-Error: Extension .%s is not linked to a '
                   'specific application!' % ext)
                   
    def need_latex_rerun(self):
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