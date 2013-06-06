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

* re-number footnotes with each chapter
* Dropcap cmd line option
* smartypants option
* Populate metadata from rst
* Cover generation
 * see http://blog.threepress.org/2009/11/20/best-practices-in-epub-cover-images/
 * Should probably convert pngs to jpegs
* Check xhtml validation

"""
from contextlib import contextmanager
import os
import sys
import tempfile

from genshi.util import striptags
import docutils
from docutils.core import Publisher, default_description, \
    default_usage
from docutils import io, nodes
from docutils.parsers.rst import Directive, directives
from docutils.readers import standalone
from docutils.writers import html4css1

try:
    import smartypants
except:
    smartypants = None

from epublib import epub


@contextmanager
def cwd_cm():
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
    yield
    os.chdir(cur_dir)


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
        self.section_title = ''
        self.authors = []
        self.cover_image = None
        self._ignore_image = False
        self.images = {}  # absolute path to book path
        self.first_page = True
        self.field_name = None
        self.fields = {}
        self.in_node = {}
        self.is_title_page = False
        self.first_paragraph = True
        self.css = ['main.css']
        self.js = []
        self.font = []  # user embedded font paths
        self.toc_parents = []
        self.toc_page = False
        self.toc_entry = True  # page that has entry in TOC and NCX
        self.parent_level = 0
        self.guide_type=None

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

    def visit_envvar(self, node):
        # !!! hook up to index when motivated
        self.visit_literal(node)

    def depart_envvar(self, node):
        self.depart_literal(node)

    def visit_paragraph(self, node):
        # All text need p's (else breaks epubcheck)
        if self.first_paragraph and not self.at('admonition'):
            if self.section_level == 1:
                self.body.append(self.starttag(node, 'p', '', **{'class':'first-para-chapter'}))
            else:
                self.body.append(self.starttag(node, 'p', '', **{'class':'first-para'}))
            self.context.append('</p>\n')

        elif self.at('admonition'):
            if self.first_paragraph:
                self.body.append(self.starttag(node, 'p', '', **{'class':'note-first-p'}))
            else:
                self.body.append(self.starttag(node, 'p', '', **{'class':'note-p'}))
            self.context.append('</p>\n')
        elif self.at('block_quote'):
            self.body.append(self.starttag(node, 'p', '', **{}))
            self.context.append('</p>\n')

        else:
            html4css1.HTMLTranslator.visit_paragraph(self, node)
        self.first_paragraph = False

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

    def visit_literal_block(self, node):
        # mobi needs an extra div here, otherwise headings following <pre> are indented poorly
        if self.at('admonition'):
            self.body.append(self.starttag(node, 'div', CLASS='div-literal-block-admonition'))
            self.body.append(self.starttag(node, 'pre', CLASS='literal-block-admonition'))
        else:
            self.body.append(self.starttag(node, 'div'))
            self.body.append(self.starttag(node, 'pre', CLASS='literal-block'))

    def depart_literal_block(self, node):
        html4css1.HTMLTranslator.depart_literal_block(self, node)
        self.body.append('</div>\n')

    def visit_meta(self, node):
        # support gutenberg extensions
        # http://www.gutenberg.org/wiki/Gutenberg:The_PG_boilerplate_for_RST
        name = node.get('name', '')
        if name.startswith('DC'):
            self.fields[name[3:]] = node.get('content')
        elif name.startswith('coverpage'):
            with cwd_cm():
                cover_page = node.get('content')
                self.cover_image = os.path.abspath(cover_page)

    @cwd_decorator
    def visit_Text(self, node):
        if "Copyright" in str(node):
            pass
        txt = node.astext()
        if self.at('field_name'):
            self.field_name = node.astext()
        elif self.at('field_body'):
            pass
        elif self.at('generated'):#  and 'sectnum' in node.get('classes'):
            # avoid <generated classes="sectnum">5.1</generated>
            pass
        elif self.at('comment'):
            if txt == 'titlepage':
                self.is_title_page = True
            elif txt.startswith('newpage:'):
                # don't create table of contents entry
                self.create_chapter()
                self.toc_entry = False
                self.section_level = 1
            elif txt.startswith('newchapter:'):
                # don't create table of contents entry
                self.create_chapter()
                self.section_level = 1
            elif txt.startswith('guide:'):
                self.guide_type=txt.split(':')[-1]
            elif txt.startswith('css:'):
                paths = txt.split(':')[-1].split(',')
                self.css = self.css + [os.path.abspath(path) for path in paths if path]
            elif txt.startswith('js:'):
                paths = txt.split(':')[-1].split(',')
                self.js = self.js + [os.path.abspath(path) for path in paths if path]
            elif txt.startswith('font:'):
                paths = txt.split(':')[-1].split(',')
                self.font = self.font + [os.path.abspath(path) for path in paths if path]
            elif txt == 'nocss':
                self.css = None
            elif txt.startswith('addimg:'):
                uri = txt.split(':')[-1]
                self.images[os.path.abspath(uri)] = uri
            elif txt.startswith('toc:show'):
                # old school hack now overriding .. contents::
                # see visit_epubcontent
                if self.body:
                    self.create_chapter()
                self.book.add_toc_page(order=self.book.next_order())
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

    def visit_epubcontent(self, node):
        if self.body:
            # create an existing chapter
            self.create_chapter()
        self.toc_page = True

    def depart_epubcontent(self, node):
        self.section_level = 0

    @cwd_decorator
    def visit_image(self, node):
        self._ignore_image = False
        if 'cover' in node.get('classes'):
            source = node.get('uri')
            self.cover_image = os.path.abspath(source)
            self._ignore_image = True
        else:
            source = node.get('uri')
            self.images[os.path.abspath(source)] = source
        if not self._ignore_image:
            # appease epubcheck
            self.body.append('<div>\n')
            html4css1.HTMLTranslator.visit_image(self, node)

    def depart_image(self, node):
        if not self._ignore_image:
            # appease epubcheck
            self.body.append('</div>\n')
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
            #pass
            # need to deal with para's that have multiple text children
            # such as foo... |copy| foo :(
            self.fields[self.field_name] = node.astext()
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

    def visit_title(self, node):
        html4css1.HTMLTranslator.visit_title(self, node)

    def depart_title(self, node):
        if self.section_level == 1:
            if self.section_title == '':
                start = self.body_len_before_node[node.__class__.__name__]
                self.section_title = ''.join(self.body[start + 1:])
        html4css1.HTMLTranslator.depart_title(self, node)

    def depart_author(self, node):
        start = self.body_len_before_node[node.__class__.__name__]
        self.authors.append(node.children[0])

    def visit_transition2(self, node):
        # hack to have titleless chapter
        self.reset_chapter()

    def visit_section(self, node):
        # too many divs is bad for mobi...
        if self.section_level == 0:
            if self.body:
                self.create_chapter()
            else:
                self.reset_chapter()
        self.section_level += 1
        self.first_paragraph = True

    def depart_section(self, node):
        self.first_page = False
        if self.section_level >= 1:
            self.section_level -= 1
        if self.section_level == 0:
            self.create_chapter()

    def visit_generated(self, node):
        pass

    #depart_generated = depart_section

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
        if self.font:
            for item in self.font:
                if os.path.exists(item):
                    self.book.add_font(item, os.path.basename(item))
                else:
                    raise KeyError
        js = ''
        if self.js:

            js = ''.join(['<script src="{0}" type="text/javascript"></script>'.format(os.path.basename(item)) for item in self.js])
            for item in self.js:
                if os.path.exists(item):
                    self.book.add_js(item, os.path.basename(item))
                else:
                    raise KeyError
        title = ''
        if 'title' in self.fields and self.is_title_page:
            title = self.fields['title']
        elif self.section_title:
            title=striptags(self.section_title)

        header = css+js
        html = XHTML_WRAPPER.format(body=body,
                                    title=title,
                                    header=header)
        if self.is_title_page:
            self.book.add_title_page(html)
            # clear out toc_map_node
            self.book.last_node_at_depth = {0:self.book.toc_map_root}

            self.is_title_page = False
        elif self.toc_page:
            self.book.add_toc_page(order=self.book.next_order())
            self.toc_page = False
        else:
            dst = '{0}.html'.format(len(self.sections))
            item = self.book.add_html('', dst, html)
            if self.guide_type:
                self.book.add_guide_item(dst, self.section_title, self.guide_type)
            self.book.add_spine_item(item)
            parent = self.toc_parents[-1] if self.toc_parents else None
            if self.toc_entry:
                node = self.book.add_toc_map_node(item.dest_path, striptags(self.section_title), parent=parent) #''.join(self.html_subtitle))
            if self.parent_level == 1:
                self.toc_parents = [node]
            elif self.parent_level == 2:
                self.toc_parents = self.toc_parents[:1] + [node]
        self.reset_chapter()

    def reset_chapter(self):
        self.section_title = ''
        self.first_paragraph = True
        self.css = ['main.css']
        self.font = []
        self.js = []
        self.parent_level = 0
        self.section_level = 0
        self.guide_type = None
        self.toc_entry = True  # page that has entry in TOC and NCX

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
        root_dir = os.path.join(tempfile.gettempdir(), 'epub')
        for k,v in self.fields.items():
            if k == 'creator':
                self.book.add_creator(v)
            elif k.lower() == 'title':
                self.book.set_title(v)
            else:
                self.book.add_meta(k, v)
        self.book.add_creator(', '.join(self.authors))
        if self.cover_image:
            self.book.add_cover(self.cover_image, title=''.join(self.title))
        for i, img_paths in enumerate(self.images.items()):
            abs_path, dst_path = img_paths
            self.book.add_image(abs_path, dst_path, id='image_{0}'.format(i))
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
{header}
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


class epubcontent(nodes.Element):
    # change normal TOC to epubcontent
    tagname = 'epubcontent'


class Index(Directive):
    """
    Directive to add entries to the index.
    """
    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {}
    count = 0

    def run(self):
        return [] #None #ignore for now
        # see sphinx.directives.other.Index for hints
        arguments = self.arguments[0].split('\n')
        targetid = 'index-%s' % Index.count
        Index.count += 1
        targetnode = nodes.target('', '', ids=[targetid])
        self.state.document.note_explicit_target(targetnode)
        indexnode = addnodes.index()
        indexnode['entries'] = ne = []
        indexnode['inline'] = False
        for entry in arguments:
            ne.extend(process_index_entry(entry, targetid))
        return [indexnode, targetnode]

class Contents(Directive):
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = { 'class': directives.class_option,
                    'local': directives.flag,
                    'depth': directives.nonnegative_int,
                    'page-numbers': directives.flag }
    def run(self):
        return [epubcontent()]


class Parser(docutils.parsers.rst.Parser):
    def __init__(self):
        directives.register_directive('contents', Contents)
        directives.register_directive('index', Index)
        docutils.parsers.rst.Parser.__init__(self)

# fix envvar !!!
from docutils import nodes
class envvar(nodes.Inline, nodes.TextElement): pass
def ignore_role(role, rawtext, text, lineno, inliner,
                       options={}, content=[]):
    return [envvar(rawtext, text)],[]

    #class envvar(Inline, TextElement):

#class envvar(nodes.Inline, nodes.TextElement): pass
#envvar = nodes.literal

from docutils.parsers.rst import roles
roles.register_local_role('envvar', ignore_role)
#roles.register_local_role('envvar', envvar)

def main(args):
    argv = None
    reader = standalone.Reader()
    reader_name = 'standalone'
    writer = EpubWriter()
    writer_name = 'epub2'
    parser = Parser()
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
