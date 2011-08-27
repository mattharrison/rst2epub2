#!/usr/bin/env python
"""
Copyright (c) 2011, matthewharrison@gmail.com
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

    Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.
    Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in
    the documentation and/or other materials provided with the
    distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


TODO:

* Dropcap cmd line option
* smartypants option
* Populate metadata from rst
* Cover generation
 * see http://blog.threepress.org/2009/11/20/best-practices-in-epub-cover-images/
 * Should probably convert pngs to jpegs
* Check xhtml validation

"""
import os
import sys


from docutils.core import Publisher, default_description, \
    default_usage
from docutils import io
from docutils.readers import standalone
from docutils.writers import html4css1

from epublib import epub

def cwd_decorator(func):
    """
    decorator to change cwd to directory containing rst for this function
    """
    def wrapper(*args, **kw):
        cur_dir = os.getcwd()
        found = False
        for arg in sys.argv:
            if arg.endswith(".rst"):
                found = arg
                break
        if found:
            directory = os.path.dirname(arg)
            if directory:
                os.chdir(directory)
        data = func(*args, **kw)
        os.chdir(cur_dir)
        return data
    return wrapper

class EpubWriter(html4css1.Writer):
    def __init__(self):
        html4css1.Writer.__init__(self)
        self.translator_class = HTMLTranslator

    def translate(self):
        self.visitor = visitor = self.translator_class(self.document)
        self.document.walkabout(visitor)
        for attr in self.visitor_attributes:
            setattr(self, attr, getattr(visitor, attr))
        self.output = self.visitor.get_output()

class HTMLTranslator(html4css1.HTMLTranslator):
    def __init__(self, document):
        html4css1.HTMLTranslator.__init__(self, document)
        self.book = epub.EpubBook()
        self.sections = []
        self.body_len_before_node = {}
        self.section_title = None
        self.authors = []
        self.cover_image = None
        self._ignore_image = False
        self.first_page = True
        self.field_name = None

    def dispatch_visit(self, node):
        # mark body length before visiting node
        self.body_len_before_node[node.__class__.__name__] = len(self.body)
        html4css1.HTMLTranslator.dispatch_visit(self, node)

    @cwd_decorator
    def visit_image(self, node):
        self._ignore_image = False
        if 'cover' in node.get('classes'):
            source = node.get('uri')
            self.cover_image = os.path.abspath(source)
            self._ignore_image = True
        if not self._ignore_image:
            html4css1.HTMLTranslator.visit_image(self, node)

    def depart_image(self, node):
        if not self._ignore_image:
            html4css1.HTMLTranslator.depart_image(self, node)

    def visit_field_list(self, node):
        if self.first_page:
            pass
        else:
            return html4css1.HTMLTranslator.visit_field_list(self, node)

    def depart_field_list(self, node):
        if self.first_page:
            pass
        else:
            return html4css1.HTMLTranslator.depart_field_list(self, node)

    def visit_field(self, node):
        if self.first_page:
            pass
        else:
            return html4css1.HTMLTranslator.visit_field(self, node)

    def depart_field(self, node):
        if self.first_page:
            pass
        else:
            return html4css1.HTMLTranslator.depart_field(self, node)

    def visit_field_body(self, node):
        if self.first_page:
            pass
        else:
            return html4css1.HTMLTranslator.visit_field_body(self, node)

    def depart_field_body(self, node):
        if self.first_page:
            pass
        else:
            return html4css1.HTMLTranslator.depart_field_body(self, node)

    def visit_field_name(self, node):
        if self.first_page:
            pass
        else:
            return html4css1.HTMLTranslator.visit_field_name(self, node)

    def depart_field_name(self, node):
        if self.first_page:
            pass
        else:
            return html4css1.HTMLTranslator.depart_field_name(self, node)

    def depart_title(self, node):
        if self.section_level == 1:
            if self.section_title is None:
                start = self.body_len_before_node[node.__class__.__name__]
                self.section_title = ''.join(self.body[start + 1:])
        html4css1.HTMLTranslator.depart_title(self, node)

    def depart_author(self, node):
        start = self.body_len_before_node[node.__class__.__name__]
        self.authors.append(node.children[0])

    def depart_section(self, node):
        html4css1.HTMLTranslator.depart_section(self, node)
        if self.section_level == 0:
            self.sections.append(self.body)
            self.body = []
            html = XHTML_WRAPPER.format(''.join(self.sections[-1]))
            item = self.book.add_html('', '{0}.html'.format(len(self.sections)), html)
            self.book.add_spine_item(item)
            self.book.add_toc_map_node(item.dest_path, self.section_title) #''.join(self.html_subtitle))
            self.section_title = None

    def get_output(self):
        root_dir = '/tmp/epub'
        self.book.add_css(os.path.join(
            os.path.dirname(epub.__file__), 'templates',
            'main.css'), 'main.css')
        self.book.set_title(''.join(self.title))

        self.book.add_creator(', '.join(self.authors))
        self.book.add_title_page()
        self.book.add_toc_page()
        if self.cover_image:
            self.book.add_cover(self.cover_image)

        self.book.create_book(root_dir)
        self.book.create_archive(root_dir, root_dir + '.epub')
        return open(root_dir + '.epub').read()

XHTML_WRAPPER = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
<title>TITLE THE PAGE HERE</title>
<meta http-equiv="Content-type" content="application/xhtml+xml;charset=utf8" />
<link rel="stylesheet" href="main.css" type="text/css" media="all" />
</head>
<body>
{0}
</body>
</html>'''


class EpubFileOutput(io.FileOutput):
    """
    A version of docutils.io.FileOutput which writes to a binary file.
    """
    def open(self):
        try:
            self.destination = open(self.destination_path, 'wb')

        except IOError, error:
            if not self.handle_io_errors:
                raise
            print >>sys.stderr, '%s: %s' % (error.__class__.__name__,
                                            error)
            print >>sys.stderr, ('Unable to open destination file for writing '
                                 '(%r).  Exiting.' % self.destination_path)
            sys.exit(1)
        self.opened = 1

def main(args):
    argv = None
    reader = standalone.Reader()
    reader_name = 'standalone'
    writer = EpubWriter()
    writer_name = 'pseudoxml'
    parser = None
    parser_name = 'restructuredtext'
    settings = None
    settings_spec = None
    settings_overrides = None
    config_section = None
    enable_exit_status = 1
    usage = default_usage
    publisher = Publisher(reader, parser, writer, settings,
                          destination_class=EpubFileOutput)
    publisher.set_components(reader_name, parser_name, writer_name)
    description = ('Generates epub books from reStructuredText sources.  ' + default_description)

    output = publisher.publish(argv, usage, description,
                               settings_spec, settings_overrides,
                               config_section=config_section,
                               enable_exit_status=enable_exit_status)

if __name__ == '__main__':
    if '--doctest' in sys.argv:
        _test()
    else:
        sys.exit(main(sys.argv) or 0)
