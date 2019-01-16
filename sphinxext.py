import os.path

import rst2epub

from docutils.frontend import OptionParser
from docutils.writers import html4css1
from epublib import epub
from genshi.util import striptags
from sphinx.builders import Builder
from sphinx.highlighting import PygmentsBridge
from sphinx.util.console import bold, darkgreen
from sphinx.util.nodes import inline_all_toctrees
from sphinx.util.osutil import copyfile, relative_uri
from sphinx.writers.html import HTMLTranslator


# dublin core meta data
DC_ITEMS = set('title', 'creator', 'subject', 'description', 'publisher',
               'contributor', 'date', 'type', 'format', 'identifier', 'source',
               'language', 'relation', 'coverage', 'rights')

class MobiWriter(html4css1.Writer):
    def __init__(self, builder):
        html4css1.Writer.__init__(self)
        self.builder = builder

    def translate(self):
        visitor = MobiTranslator(self.builder, self.document)
        self.document.walkabout(visitor)
        self.output = visitor.get_output()


class MobiTranslator(HTMLTranslator):
    def __init__(self, builder, document, *args, **kwargs):
        HTMLTranslator.__init__(self, builder, document, *args, **kwargs)
        self._title = None  # section title
        self.parent = None
        self.add_to_toc = False
        self.order = 0
        self.add_permalinks = False
        self.css = ['main.css']
        self._images = set()
        self.doc_path = document.attributes['source']

    def visit_compound(self, node):
        # print "COMPOUND", node
        # only adding items to table of contents if in toctree
        if 'toctree-wrapper' in node['classes']:
            try:
                self.builder.ebook.add_toc_page(order=self.next_order())
            except AssertionError:
                pass
            self.add_to_toc = True

    def depart_compound(self, node):
        if 'toctree-wrapper' in node['classes']:
            self.add_to_toc = False

    def next_order(self):
        val = self.order
        self.order += 1
        return val

    def dispatch_visit(self, node):
        """
        Call self."``visit_`` + node class name" with `node` as
        parameter.  If the ``visit_...`` method does not exist, call
        self.unknown_visit.
        """
        node_name = node.__class__.__name__
        method = getattr(self, 'visit_' + node_name, self.unknown_visit)
        self.document.reporter.debug(
            'docutils.nodes.NodeVisitor.dispatch_visit calling %s for %s'
            % (method.__name__, node_name))
        return method(node)

    def create_chapter(self):
        body = ''.join(self.body)
        self.body = []
        book = self.builder.ebook
        # check for css overrides
        css_pattern = \
            '<link rel="stylesheet" href="{0}" type="text/css" media="all" />'
        css = ''
        for item in self.css:
            css += css_pattern.format(os.path.basename(item)) + '\n'
        css = css.rstrip()

        src_css = os.path.join(os.path.dirname(rst2epub.epub.__file__),
                               'templates', 'main.css')
        dst_css = 'main.css'
        book.add_css(src_css, dst_css)
        src_path = ''
        if self._title is None:
            print "NONE TITLE"
            self._title = ''
        dst_path = '{0}.html'.format(self.next_order())
        html = rst2epub.XHTML_WRAPPER.format(body=body,
                                             title=self._title,
                                             css=css)
        item = book.add_html(src_path, dst_path, html)
        book.add_spine_item(item)
        if self.add_to_toc:
            book.add_toc_map_node(item.dest_path,
                                  self._title)
        self._title = None
        self.parent = None

    def get_output(self):
        return self.builder.get_output_data()

    def implement_me(self, *args):
        print "FILL IN"

    def visit_image(self, node):
        olduri = node['uri']
        import pdb
        pdb.set_trace()
        # rewrite the URI if the environment knows about it
        # if olduri in self.builder.images:
        #     node['uri'] = posixpath.join(self.builder.imgpath,
        #                                  self.builder.images[olduri])
        #                                  #import pdb; pdb.set_trace()
        print "IMAGE!!!", node, node['uri'], os.path.abspath(node['uri'])
        if os.path.abspath(olduri) != olduri:
            pass
            # # relative
            # dest = os.path.join(self.builder.outdir,olduri)
            # print "COPYING TO", dest
            # olduri = os.path.join(os.path.dirname(self.doc_path),
            #                    dest)
        self._images.add(os.path.abspath(olduri))
        self.builder.ebook.add_image(os.path.abspath(olduri),
                                     olduri,
                                     id='image_{0}'.format(len(self._images)))
        HTMLTranslator.visit_image(self, node)

    def visit_section(self, node):
        print "\n\nSEC", self.section_level, str(node)[:120]
        self.section_level += 1

    def depart_section(self, node):
        self.section_level -= 1
        if self.section_level <= int(self.builder.config.mobi_chapter_level):
            print "CREATE CHAPTER"
            self.create_chapter()

    def depart_title(self, node):
        # print "--TITLE", node.text
        if not self._title:
            self._title = striptags(''.join(self.body[1:]))
        print "\n\n**title", self.section_level, ''.join(self.body[1:])[:150]
        low_level = self.section_level \
            <= int(self.builder.config.mobi_chapter_level)
        if node.parent.getattr('ids', False) and low_level:
            print "TITLE", self.section_level, node.parent['ids'][0]
            self._title = striptags(''.join(self.body[1:]))
            print "\t", str(node)[:50]
            print "\tBODY", self.body[:4]
        else:
            print "FALSE"
        HTMLTranslator.depart_title(self, node)

    depart_pending_xref = visit_pending_xref = implement_me

    def no_op(self, node):
        pass

    visit_start_of_file = no_op


class MobiBuilder(Builder):
    # basing off of latex since it seems more straightforward
    name = 'mobi'
    out_suffix = '.epub'
    add_permalinks = True

    def init(self):
        # note not dunder!
        self.ebook = epub.EpubBook()
        assert self.config.mobi_title
        self.ebook.set_title(self.config.mobi_title)
        if self.config.mobi_cover:
            self.ebook.add_cover(self.config.mobi_cover[0],
                                 title=self.config.mobi_title)
        self.do_dublin_core()
        self.document_data = []
        self.docnames = []
        self.secnumbers = {}
        self.init_highlighter()

    def do_dublin_core(self):
        for key in self.config.values:
            value = getattr(self.config, key)
            if not value:
                continue
            if key.startswith('mobi_'):
                key = key[len('mobi_'):].lower()
                if key in DC_ITEMS:
                    if key == 'title':
                        continue
                    print "\t***ADDING", key, value
                    self.ebook.add_meta(key, value)

    def init_highlighter(self):
        # determine Pygments style and create the highlighter
        if self.config.pygments_style is not None:
            style = self.config.pygments_style
        elif self.theme:
            style = self.theme.get_confstr('theme', 'pygments_style', 'none')
        else:
            style = 'sphinx'
        self.highlighter = PygmentsBridge('html', style,
                                          self.config.trim_doctest_flags)

    def get_outdated_docs(self):

        return 'all documents'

    def get_target_uri(self, docname, typ=None):
        return docname + '.html'

    def get_relative_uri(self, from_, to, typ=None):
        # ignore source path
        return self.get_target_uri(to, typ)

    def write(self, *ignored):
        writer = MobiWriter(self)
        docsettings = OptionParser(
            defaults=self.env.settings,
            components=(writer,)).get_default_values()
        doc_name = self.config.master_doc
        self.imgpath = relative_uri(self.get_target_uri(doc_name), '_images')
        tree = self.env.get_doctree(doc_name)
        master = self.config.master_doc
        tree = inline_all_toctrees(self, set(), master, tree, darkgreen)
        # copy images into self.images
        self.post_process_images(tree)
        targetname = self.config.project + '.epub'
        tree.settings = docsettings
        writer.write(
            tree,
            rst2epub.EpubFileOutput(
                destination_path=os.path.join(self.outdir, targetname)))

    def get_output_data(self):
        root_dir = '/tmp/mobiext'
        self.ebook.create_book(root_dir)
        book_name = root_dir + '.epub'
        self.ebook.create_archive(root_dir, book_name)

        if book_name.endswith('.epub'):
            import subprocess
            cmd = "kindlegen2.4 {0}".format(book_name)
            print "RUNNING", cmd
            subprocess.call(cmd, shell=True)

        return open(root_dir + '.epub').read()

    def finish(self):
        # copy image files
        if self.images:
            self.info(bold('copying images...'), nonl=1)
            for src, dest in self.images.iteritems():
                self.info(' '+src, nonl=1)
                dest_file = os.path.join(self.outdir, dest)
                copyfile(os.path.join(self.srcdir, src),
                         dest_file)
            self.info()
        print "FIN"


def setup(app):
    app.add_builder(MobiBuilder)
    app.add_stylesheet('epublib/templates/main.css')

    app.add_config_value('mobi_cover', None, None)
    # chapter level is depth at which new chapters are created
    app.add_config_value('mobi_chapter_level', 2, None)
    for name in DC_ITEMS:
        app.add_config_value('mobi_'+name, None, None)
