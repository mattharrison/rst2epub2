# -*- coding: utf-8 -*-
"""
Copyright (c) 2011, timtambin@gmail.com
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
"""
import itertools
import mimetypes
import os
import shutil
import subprocess
import uuid
import zipfile


from genshi.template import TemplateLoader
try:
    from lxml import etree
except ImportError as e:
    # no xpath support!
    import xml.etree.ElementTree as etree


COVER_ORDER = -300
TITLE_ORDER = -200
TOC_ORDER = -100

class TocMapNode:

    def __init__(self):
        self.play_order = 0
        self.title = ''
        self.href = ''
        self.children = []
        self.depth = 0

    def assign_play_order(self):
        next_play_order = [0]
        self._assign_play_order(next_play_order)

    def _assign_play_order(self, next_play_order):
        self.play_order = next_play_order[0]
        next_play_order[0] = self.play_order + 1
        for child in self.children:
            child._assign_play_order(next_play_order)


class EpubItem:

    def __init__(self):
        self.id = ''
        self.src_path = ''
        self.dest_path = ''
        self.mime_type = ''
        self.html = ''


class EpubBook:

    def __init__(self):
        #self.loader = TemplateLoader('epublib/templates')
        temp_dir = os.path.dirname(os.path.abspath(__file__))
        self.loader = TemplateLoader(os.path.join(temp_dir,'templates'))

        self.root_dir = ''
        self.UUID = uuid.uuid1()

        self.lang = 'en-US'
        self.title = ''
        self.creators = []
        self.meta_info = []

        self.image_items = {}
        self.html_items = {}
        self.css_items = {}
        self.js_items = {}
        self.font_items = {}


        self.cover_image = None
        self.title_page = None
        self.toc_page = None

        self.spine = []
        self.guide = {}
        self.toc_map_root = TocMapNode()
        self.last_node_at_depth = {0 : self.toc_map_root}


    def set_title(self, title):
        self.title = title

    def set_lang(self, lang):
        self.lang = lang

    def add_creator(self, name, role = 'aut'):
        self.creators.append((name, role))

    def add_meta(self, meta_name, meta_value, **meta_attrs):
        self.meta_info.append((meta_name, meta_value, meta_attrs))

    def get_meta_tags(self):
        l = []
        for meta_name, meta_value, meta_attr in self.meta_info:
            begin_tag = '<dc:%s' % meta_name
            if meta_attr:
                for attr_name, attr_value in meta_attr.iteritems():
                    begin_tag += ' opf:%s="%s"' % (attr_name, attr_value)
            begin_tag += '>'
            end_tag = '</dc:%s>' % meta_name
            l.append((begin_tag, meta_value, end_tag))
        return l

    def get_image_items(self):
        return sorted(self.image_items.values(), key = lambda x : x.id)

    def get_html_items(self):
        return sorted(self.html_items.values(), key = lambda x : x.id)

    def get_css_items(self):
        return sorted(self.css_items.values(), key = lambda x : x.id)

    def get_js_items(self):
        return sorted(self.js_items.values(), key = lambda x : x.id)

    def get_all_items(self):
        return sorted(itertools.chain(self.image_items.values(), self.html_items.values(), self.css_items.values(), self.js_items.values(), self.font_items.values()), key = lambda x : x.id)

    def add_image(self, src_path, dest_path, id=None):
        if dest_path in self.image_items:
            return
        item = EpubItem()
        item.id = id or 'image_{0}'.format(len(self.image_items) + 1)
        item.src_path = src_path
        item.dest_path = dest_path
        item.mime_type = mimetypes.guess_type(dest_path)[0]
        #assert item.dest_path not in self.image_items
        self.image_items[dest_path] = item
        return item


    def add_html(self, src_path, dest_path, html, id=None):
        item = EpubItem()
        item.id = id or 'html_%04d' % (len(self.html_items) + 1)
        item.src_path = src_path
        item.dest_path = dest_path
        item.html = html
        item.mime_type = 'application/xhtml+xml'
        assert item.dest_path not in self.html_items
        self.html_items[item.dest_path] = item
        return item

    def add_font(self, src_path, dest_path):
        if dest_path in self.font_items:
            return
        item = EpubItem()
        item.id = 'font_%d' % (len(self.font_items) + 1)
        item.src_path = src_path
        item.dest_path = dest_path
        if src_path.endswith('otf'):
            item.mime_type = 'application/opentype'
        elif src_path.endswith('ttf'):
            item.mime_type = 'application/truetype'
        else:
            raise KeyError
        #assert item.dest_path not in self.font_items
        self.font_items[item.dest_path] = item
        return item

    def add_js(self, src_path, dest_path):
        if dest_path in self.js_items:
            return
        item = EpubItem()
        item.id = 'js_%d' % (len(self.css_items) + 1)
        item.src_path = src_path
        item.dest_path = dest_path
        item.mime_type = 'text/javascript'
        #assert item.dest_path not in self.css_items
        self.js_items[item.dest_path] = item
        return item

    def add_css(self, src_path, dest_path):
        if dest_path in self.css_items:
            return
        item = EpubItem()
        item.id = 'css_%d' % (len(self.css_items) + 1)
        item.src_path = src_path
        item.dest_path = dest_path
        item.mime_type = 'text/css'
        #assert item.dest_path not in self.css_items
        self.css_items[item.dest_path] = item
        return item

    def add_cover(self, src_path, title='_cover'):
        assert not self.cover_image
        _, ext = os.path.splitext(src_path)
        dest_path = 'cover%s' % ext
        self.cover_image = self.add_image(src_path, dest_path, id='cover-image')
        cover_page = self.add_cover_html_for_image(self.cover_image, title)
        self.add_spine_item(cover_page, False, COVER_ORDER)
        self.add_guide_item(cover_page.dest_path, title, 'cover')

    def add_cover_html_for_image(self, image_item, title):
        tmpl = self.loader.load('image.html')
        image_item.title = title
        stream = tmpl.generate(book=self, item=image_item)
        html = stream.render('xhtml', doctype='xhtml11', drop_xml_decl=False)
        return self.add_html('', 'cover.html', html, id='cover')

    def _make_title_page(self):
        assert self.title_page
        if self.title_page.html:
            return
        tmpl = self.loader.load('title-page.html')
        stream = tmpl.generate(book = self)
        self.title_page.html = stream.render('xhtml', doctype = 'xhtml11', drop_xml_decl = False)

    def add_title_page(self, html=''):
        assert not self.title_page
        self.title_page = self.add_html('', 'title-page.html', html)
        self.add_spine_item(self.title_page, True, TITLE_ORDER)
        self.add_guide_item('title-page.html', 'Title Page', 'title-page')

    def _make_toc_page(self):
        assert self.toc_page
        tmpl = self.loader.load('toc.html')
        stream = tmpl.generate(book=self)
        self.toc_page.html = stream.render('xhtml', doctype = 'xhtml11', drop_xml_decl = False)

    def add_toc_page(self, order=TOC_ORDER):
        assert not self.toc_page
        self.toc_page = self.add_html('', 'toc.html', '')
        self.add_spine_item(self.toc_page, False, order)
        self.add_guide_item('toc.html', 'Table of Contents', 'toc')

    def get_spine(self):
        results = sorted(self.spine)
        return results

    def next_order(self):
        order = (max(order for order, _, _ in self.spine) if self.spine else 0) + 1
        return order

    def add_spine_item(self, item, linear=True, order=None):
        assert item.dest_path in self.html_items
        if order is None:
            order = self.next_order()
        self.spine.append((order, item, linear))

    def get_guide(self):
        return sorted(self.guide.values(), key = lambda x : x[2])

    def add_guide_item(self, href, title, type):
        assert type not in self.guide, "TYPE %s NOT IN GUIDE %s"%(type, self.guide)
        self.guide[type] = (href, title, type)

    def get_toc_map_root(self):
        return self.toc_map_root

    def get_toc_map_height(self):
        return max(self.last_node_at_depth.keys())

    def add_toc_map_node(self, href, title, depth=None, parent=None):
        node = TocMapNode()
        node.href = href
        node.title = title
        if parent == None:
            if depth == None:
                parent = self.toc_map_root
            else:
                parent = self.last_node_at_depth[depth - 1]
        parent.children.append(node)
        node.depth = parent.depth + 1
        self.last_node_at_depth[node.depth] = node
        return node

    def make_dirs(self):
        try:
            os.makedirs(os.path.join(self.root_dir, 'META-INF'))
        except OSError:
            pass
        try:
            os.makedirs(os.path.join(self.root_dir, 'OEBPS'))
        except OSError:
            pass

    def _write_container_xml(self):
        fout = open(os.path.join(self.root_dir, 'META-INF', 'container.xml'), 'wb')
        tmpl = self.loader.load('container.xml')
        stream = tmpl.generate()
        fout.write(stream.render('xml'))
        fout.close()

    def _write_toc_ncx(self):
        self.toc_map_root.assign_play_order()
        fout = open(os.path.join(self.root_dir, 'OEBPS', 'toc.ncx'), 'wb')
        tmpl = self.loader.load('toc.ncx')
        stream = tmpl.generate(book=self)
        fout.write(stream.render('xml'))
        fout.close()

    def _write_content_opf(self):
        fout = open(os.path.join(self.root_dir, 'OEBPS', 'content.opf'), 'wb')
        tmpl = self.loader.load('content.opf')
        stream = tmpl.generate(book=self)
        data = stream.render('xml')
        fout.write(data)
        fout.close()

    def _write_items(self):
        for item in self.get_all_items():
            if item.html:
                fout = open(os.path.join(self.root_dir, 'OEBPS', item.dest_path), 'wb')
                if isinstance(item.html, str):
                    fout.write(item.html)
                else:
                    fout.write(item.html.encode('utf-8'))
                fout.close()
            else:
                put_file(item.src_path, os.path.join(self.root_dir, 'OEBPS', item.dest_path))


    def _write_mime_type(self):
        fout = open(os.path.join(self.root_dir, 'mimetype'), 'wb')
        fout.write('application/epub+zip')
        fout.close()

    @staticmethod
    def _list_manifest_items(content_opf_path):
        tree = etree.parse(content_opf_path)
        #return tree.xpath("//opf:manifest/opf:item/@href", namespaces = {'opf': 'http://www.idpf.org/2007/opf'})
        return [foo.attrib['href'] for foo in tree.findall('{http://www.idpf.org/2007/opf}manifest/{http://www.idpf.org/2007/opf}item')]

    @staticmethod
    def create_archive(root_dir, output_path):
        fout = zipfile.ZipFile(output_path, 'w')
        cwd = os.getcwd()
        os.chdir(root_dir)
        fout.writestr('mimetype', 'application/epub+zip',
                      compress_type=zipfile.ZIP_STORED)
        fileList = []
        fileList.append(os.path.join('META-INF', 'container.xml'))
        fileList.append(os.path.join('OEBPS', 'content.opf'))
        for item_path in EpubBook._list_manifest_items(os.path.join('OEBPS', 'content.opf')):
            fileList.append(os.path.join('OEBPS', item_path))
        for file_path in fileList:
            fout.write(file_path, compress_type=zipfile.ZIP_DEFLATED)
        fout.close()
        os.chdir(cwd)

    @staticmethod
    def check_epub(checker_path, epub_path):
        subprocess.call(['java', '-jar', checker_path, epub_path], shell = True)

    def create_book(self, root_dir):
        if self.title_page:
            self._make_title_page()
        if self.toc_page:
            self._make_toc_page()
        self.root_dir = root_dir
        self.make_dirs()
        self._write_mime_type()
        self._write_items()
        self._write_container_xml()
        self._write_content_opf()
        self._write_toc_ncx()


def put_file(abs_path, rel_path):
    """
    given a file put it in the rel_path creating necessary dirs
    """
    parents = os.path.dirname(rel_path)
    try:
        os.makedirs(parents)

    except OSError, e:
        import errno
        if e.errno != errno.EEXIST or not os.path.isdir(parents):
            raise
    shutil.copyfile(abs_path, rel_path)

def test():
    def get_minimal_html(text):
        return """<!DOCTYPE html PUBLIC "-//W3C//DTD XHtml 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>%s</title></head>
<body><p>%s</p></body>
</html>
""" % (text, text)

    book = EpubBook()
    book.set_title('Most Wanted Tips for Aspiring Young Pirates')
    book.add_creator('Monkey D Luffy')
    book.add_creator('Guybrush Threepwood')
    book.add_meta('contributor', 'Smalltalk80', role = 'bkp')
    book.add_meta('date', '2010', event = 'publication')

    book.add_title_page()
    book.add_toc_page()
    book.add_cover(r'D:\epub\blank.png')

    book.add_css(r'main.css', 'main.css')

    n1 = book.add_html('', '1.html', get_minimal_html('Chapter 1'))
    n11 = book.add_html('', '2.html', get_minimal_html('Section 1.1'))
    n111 = book.add_html('', '3.html', get_minimal_html('Subsection 1.1.1'))
    n12 = book.add_html('', '4.html', get_minimal_html('Section 1.2'))
    n2 = book.add_html('', '5.html', get_minimal_html('Chapter 2'))

    book.add_spine_item(n1)
    book.add_spine_item(n11)
    book.add_spine_item(n111)
    book.add_spine_item(n12)
    book.add_spine_item(n2)

    # You can use both forms to add TOC map
    #t1 = book.add_toc_map_node(n1.dest_path, '1')
    #t11 = book.add_toc_map_node(n11.dest_path, '1.1', parent = t1)
    #t111 = book.add_toc_map_node(n111.dest_path, '1.1.1', parent = t11)
    #t12 = book.add_toc_map_node(n12.dest_path, '1.2', parent = t1)
    #t2 = book.add_toc_map_node(n2.dest_path, '2')

    book.add_toc_map_node(n1.dest_path, '1')
    book.add_toc_map_node(n11.dest_path, '1.1', 2)
    book.add_toc_map_node(n111.dest_path, '1.1.1', 3)
    book.add_toc_map_node(n12.dest_path, '1.2', 2)
    book.add_toc_map_node(n2.dest_path, '2')

    root_dir = r'd:\epub\test'
    book.create_book(root_dir)
    EpubBook.create_archive(root_dir, root_dir + '.epub')
    EpubBook.check_epub('epubcheck-1.0.5.jar', root_dir + '.epub')

if __name__ == '__main__':
    test()
