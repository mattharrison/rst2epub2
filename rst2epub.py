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

from genshi.util import striptags
from docutils.core import Publisher, default_description, \
    default_usage
from docutils import io, nodes
from docutils.readers import standalone
from docutils.writers import html4css1

try:
    import smartypants
except:
    smartypants = None

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
        self.images = []
        self.first_page = True
        self.field_name = None
        self.fields = {}
        self.in_node = {}
        self.is_title_page = False
        self.first_paragraph = True
        self.css = ['main.css']
        self.toc_parents = []
        self.toc_page = False
        self.parent_level = 0


    def dispatch_visit(self, node):
        # mark body length before visiting node
        self.body_len_before_node[node.__class__.__name__] = len(self.body)
        # keep track of parents
        count = self.in_node.setdefault(node.tagname, 0)
        self.in_node[node.tagname] += 1
        html4css1.HTMLTranslator.dispatch_visit(self, node)

    def dispatch_departure(self, node):
        try:
            self.in_node[node.tagname] -= 1
        except KeyError as e:
            print node.tagname
        html4css1.HTMLTranslator.dispatch_departure(self, node)

    def at(self, nodename):
        """
        shortcut for at/under this node
        """
        return self.in_node.get(nodename, False)

    def _dumb(self, node):
        pass
    visit_comment = _dumb
    depart_comment = _dumb


    def visit_paragraph(self, node):
        if self.should_be_compact_paragraph(node):
            self.context.append('')
        elif self.first_paragraph and not self.at('admonition'):
            self.body.append(self.starttag(node, 'p', '', **{'class':'first-para'}))
            self.context.append('</p>\n')

        elif self.at('admonition'):
            if self.first_paragraph:
                self.body.append(self.starttag(node, 'p', '', **{'class':'note-first-p'}))
            else:
                self.body.append(self.starttag(node, 'p', '', **{'class':'note-p'}))
            self.context.append('</p>\n')

        else:
             #if 1:
            html4css1.HTMLTranslator.visit_paragraph(self, node)
        self.first_paragraph = False
    # def depart_paragraph(self, node):
    #     if self.first_paragraph:

    def append_class_on_child(self, node, class_, index=0):
        children = [n for n in node if not isinstance(n, nodes.Invisible)]
        try:
            child = children[index]
        except IndexError:
            return
        # should only be one class
        if child['classes']:
            child['classes'] = child['classes'][0] + class_

    def set_first_last(self, node):
        # mobi doesn't like multiple classes per tag
        self.append_class_on_child(node, '-first', 0)
        #self.append_class_on_child(node, '-last', -1)

    # def visit_admonition(self, node):
    #     # mobi don't like those divs, messes up formatting on subsequent elements
    #     pass
    # def depart_admonition(self, node):
    #     pass

    def visit_literal_block(self, node):
        # mobi needs an extra div here, otherwise headings following <pre> are indented poorly
        if self.at('admonition'):
            self.body.append(self.starttag(node, 'div', CLASS='div-literal-block-admonition'))
            self.body.append(self.starttag(node, 'pre', CLASS='literal-block-admonition'))
        else:
            self.body.append(self.starttag(node, 'div'))
            self.body.append(self.starttag(node, 'pre', CLASS='literal-block'))
        #html4css1.HTMLTranslator.visit_literal_block(self, node)

    def depart_literal_block(self, node):
        html4css1.HTMLTranslator.depart_literal_block(self, node)
        self.body.append('</div>\n')


    def visit_title(self, node):
        html4css1.HTMLTranslator.visit_title(self, node)


    @cwd_decorator
    def visit_Text(self, node):
        txt = node.astext()
        if self.at('field_name'):
            self.field_name = node.astext()
        elif self.at('field_body'):
            self.fields[self.field_name] = node.astext()
            self.field_name = None
        elif self.at('comment'):
            if txt == 'titlepage':
                self.is_title_page = True
            elif txt.startswith('css:'):
                paths = txt.split(':')[-1].split(',')
                self.css = [os.path.abspath(path) for path in paths if path]
            elif txt == 'nocss':
                self.css = None
            elif txt.startswith('addimg:'):
                self.images.append(os.path.abspath(txt.split(':')[-1]))
            elif txt.startswith('toc:show'):
                self.toc_page = True
            elif txt.startswith('toc:parent1'):
                self.is_parent = True
                self.parent_level = 1
                self.toc_parents = []
            elif txt.startswith('toc:parent2'):
                self.is_parent = True
                self.parent_level = 2
            elif txt.startswith('toc:clear'):
                self.is_parent = False
                self.toc_parents = []

        else:
            html4css1.HTMLTranslator.visit_Text(self, node)

    @cwd_decorator
    def visit_image(self, node):
        self._ignore_image = False
        if 'cover' in node.get('classes'):
            source = node.get('uri')
            self.cover_image = os.path.abspath(source)
            self._ignore_image = True
        else:
            source = node.get('uri')
            self.images.append(os.path.abspath(source))
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

    def visit_transition(self, node):
        # hack to have titleless chapter
        self.reset_chapter()

    def visit_section(self, node):
        # too many divs is bad for mobi...
        #html4css1.HTMLTranslator.visit_section(self, node)
        if self.section_level == 0:
            if self.body:
                self.create_chapter()
            else:
                self.reset_chapter()
        self.section_level += 1
        self.first_paragraph = True




    def depart_section(self, node):
        self.first_page = False
        self.section_level -= 1
        #html4css1.HTMLTranslator.depart_section(self, node)
        if self.section_level == 0:
            self.create_chapter()

    def create_chapter(self):
        self.sections.append(self.body)
        self.body = []
        body = ''.join(self.sections[-1])
        if smartypants:
            #body = smartypants.smartyPants(body)
            # pass need to ignore pre contents...
            pass
        css = ''
        if self.css:
            css = ''.join(['<link rel="stylesheet" href="{0}" type="text/css" media="all" />'.format(os.path.basename(item)) for item in self.css])
            for item in self.css:
                if os.path.exists(item):
                    self.book.add_css(item, os.path.basename(item))
                else:
                    self.book.add_css(os.path.join(os.path.dirname(epub.__file__),
                                      'templates',
                                      'main.css'),'main.css')
        title = ''
        if self.section_title:
            title=striptags(self.section_title)

        html = XHTML_WRAPPER.format(body=body,
                                    title=title,
                                    css=css)

        if self.is_title_page:
            self.book.add_title_page(html)
            # clear out toc_map_node
            self.book.last_node_at_depth = {0:self.book.toc_map_root}

            self.is_title_page = False
        elif self.toc_page:
            self.book.add_toc_page(order=self.book.next_order())
            self.toc_page = False
        else:
            item = self.book.add_html('', '{0}.html'.format(len(self.sections)), html)
            self.book.add_spine_item(item)
            parent = self.toc_parents[-1] if self.toc_parents else None
            node = self.book.add_toc_map_node(item.dest_path, striptags(self.section_title), parent=parent) #''.join(self.html_subtitle))
            if self.parent_level == 1:
                self.toc_parents = [node]
            elif self.parent_level == 2:
                self.toc_parents = self.toc_parents[:1] + [node]
        self.reset_chapter()

    def reset_chapter(self):
        self.section_title = None
        #self.in_node = {}
        self.first_paragraph = True
        self.css = ['main.css']
        self.parent_level = 0
        self.section_level = 0

    def visit_tgroup(self, node):
        # don't want colgroup
        node.stubs = []
        pass

    def visit_tbody(self, node):
        # don't want tbody
        pass

    def depart_tbody(self, node):
        pass

    visit_thead=visit_tbody
    depart_thead=depart_tbody

    def get_output(self):
        root_dir = '/tmp/epub'
        for k,v in self.fields.items():
            if k == 'creator':
                self.book.add_creator(v)
            else:
                self.book.add_meta(k, v)
        # self.book.add_css(os.path.join(
        #     os.path.dirname(epub.__file__), 'templates',
        #     'main.css'), 'main.css')
        self.book.set_title(''.join(self.title))

        self.book.add_creator(', '.join(self.authors))
        # add a rst comment .. titlepage to denote title page
        #self.book.add_title_page()
        #self.book.add_toc_page(order=self.toc_loc)
        if self.cover_image:
            self.book.add_cover(self.cover_image, title=''.join(self.title))
        for i, img_path in enumerate(self.images):
            parents, name = os.path.split(img_path)
            self.book.add_image(img_path, name, id='image_{0}'.format(i))
        self.book.create_book(root_dir)
        self.book.create_archive(root_dir, root_dir + '.epub')
        return open(root_dir + '.epub').read()

XHTML_WRAPPER = u'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
<title>{title}</title>
<meta http-equiv="Content-type" content="application/xhtml+xml;charset=utf8" />
{css}
</head>
<body>
{body}
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
    writer_name = 'epub2'
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
