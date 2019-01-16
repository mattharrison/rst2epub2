from __future__ import print_function

import io
import logging
import math

from epublib import epub
from genshi.core import Markup

logging.basicConfig(level=logging.DEBUG)
# see http://blog.epubandebookhelp.com/2012/05/16/kf8-panel-magnification/
# and amazon sample book
# http://mathorsinfotech.blogspot.com/2012/06/kf8-fixed-layout-image-zoom-tutorial.html
class MobiComicBook(epub.EpubBook):
    def __init__(
        self,
        width=600,
        height=1024,
        book_type="comic",
        region_magnification="true",
        orientation_lock="none",
        add_jquery=False,
    ):
        epub.EpubBook.__init__(self)
        self.comic_meta = []
        self.add_comic_meta("fixed-layout", "true")
        self.add_comic_meta("orientation-lock", "portrait")
        self.add_comic_meta("RegionMagnification", "true")
        self.width = width
        self.height = height
        resolution = "{0}x{1}".format(width, height)
        self.add_comic_meta("original-resolution", resolution)
        # if book type not specified images limited to 256K
        self.add_comic_meta("book-type", book_type)

        self.add_comic_meta("zero-gutter", "true")
        self.add_comic_meta("zero-margin", "true")

        self.pages = []
        self.page = None
        self.ordinal = 1
        self.target_id = 1

        self.add_jquery = add_jquery

    def get_target_id(self):
        tid = "zoom{0}".format(self.target_id)
        self.target_id += 1
        return tid

    def get_ordinal(self):
        # appears to be global for book
        self.ordinal += 1
        return self.ordinal - 1

    def get_meta_tags(self):
        tags = epub.EpubBook.get_meta_tags(self)
        value = end = ""
        for name, content in self.comic_meta:
            tags.append(
                ('<meta name="{0}" content="{1}"/>'.format(name, content), value, end)
            )
        return tags

    def add_comic_meta(self, name, content):
        self.comic_meta.append((name, content))

    def add_page(self):
        page = Page(self)
        self.pages.append(page)
        return page


class Mag(object):
    def __init__(
        self,
        txt,
        target_id_parent,
        target_id,
        left,
        top,
        width,
        height,
        lb_left,
        lb_top,
        lb_width,
        lb_height,
        zoomed_img_left,
        zoomed_img_top,
        img_src,
        ordinal=None,
        zoom_factor=1.5,
        pre_data=None,
        post_data=None,
    ):
        self.txt = txt
        self.target_id_parent = target_id_parent
        self.target_id = target_id

        # coordinates for click target
        self.top = top
        self.left = left
        self.height = height
        self.width = width

        # lb_ refers to lightbox image
        self.lb_top = lb_top
        self.lb_left = lb_left
        self.lb_width = lb_width
        self.lb_height = lb_height

        # zoomed_img_ referes to position on zoomed image relative to lightbox
        self.zoomed_img_top = zoomed_img_top
        self.zoomed_img_left = zoomed_img_left

        self.ordinal = ordinal
        self.zoom_factor = zoom_factor
        self.img_src = img_src
        # text/etc to display
        if post_data:
            self.post_data = Markup(post_data)
        else:
            self.post_data = ""
        if pre_data:
            self.pre_data = Markup(pre_data)
        else:
            self.pre_data = ""

    @property
    def target_id_mag(self):
        return self.target_id + "-magTarget"

    def json_junk(self):
        # kf8 really cares about double quotes on the inside...
        # only took 33 attempts to figure this out
        result = '{{"targetId":"{0}", "ordinal":{1} }}'.format(
            self.target_id_parent, self.ordinal
        )
        return result


LEFT = 1
RIGHT = 2
DOWN = 3
UP = 4


class Page(object):
    PARENT_SUFFIX = "-magTargetParent"

    def __init__(self, book, height=1024, width=600):
        self.img = None
        self.book = book
        self.mags = []
        self.title = None
        self.style = None
        self.height = height
        self.width = width

    def __iter__(self):
        for mag in self.mags:
            yield mag

    def add_bg_image(self, src_path, dest_path, id=None):
        self.img = self.book.add_image(src_path, dest_path, id)

    def auto_target(
        self,
        whtarget_left,
        whtarget_top,
        whtarget_width,
        whtarget_height,
        zoom_factor=2,
        overlap_percent=10,
        direction=LEFT,
        post_data=None,
        txt=None,
    ):
        start_left = whtarget_left
        # target is all in percent
        print("ZF", zoom_factor)
        if direction == LEFT:
            chunks = whtarget_width * zoom_factor / 100.0
            chunk_int = int(math.ceil(chunks))
            target_left = whtarget_left
            zoom_left = whtarget_left
            print("CHUNKS", chunks, "WHOLE WIDTH", whtarget_width)
            for i in range(chunk_int):
                if chunks > 1:
                    target_width = whtarget_width / float(chunks)
                else:
                    target_width = whtarget_width
                right_side = target_left + target_width
                if right_side > 100:  # whtarget_width:
                    # target_width = right_side - target_left
                    target_left = 100 - target_width
                    zoom_left = 100 - target_width
                elif right_side > start_left + whtarget_width:
                    print("OFF RIGHT")
                    target_left = whtarget_left + whtarget_width - target_width
                    zoom_left = whtarget_left + whtarget_width - target_width
                    # target_width = whtarget_width # - target_left
                print("LEFT", target_left)
                print("RIGHT SIDE", right_side, "TW", target_width)

                print(
                    "H", self.book.height, "MINUS", -whtarget_height * zoom_factor / 2.0
                )
                lb_width = 100
                lb_left = 0
                if whtarget_width * zoom_factor < 100:
                    print("SMALLER", whtarget_width * zoom_factor)
                    lb_width = whtarget_width * zoom_factor
                    lb_left = 50 - lb_width / 2
                calculated_zoom_something = (
                    whtarget_top / float(whtarget_height) / zoom_factor
                )
                calculated_zoom_something = 0 - 100 * calculated_zoom_something
                self.add_zoom_image(
                    zoom_factor,
                    target_left,
                    whtarget_top,
                    target_width,
                    whtarget_height,
                    lb_left,
                    50.0 - whtarget_height * zoom_factor / 2.0,
                    lb_width,
                    whtarget_height * zoom_factor,
                    -zoom_left,
                    calculated_zoom_something,
                    txt=txt,
                    post_data=post_data,
                )
                # zoom_left, -whtarget_top*zoom_factor)

                zoom_left += target_width
                target_left += whtarget_width / float(chunks)
                # target_left += (whtarget_width - target_width)/float(chunks)

    def add_zoom_image(
        self,
        zoom_factor,
        target_left,
        target_top,
        target_width,
        target_height,
        lb_left,
        lb_top,
        lb_width,
        lb_height,
        zoom_left,
        zoom_top,
        src_path=None,
        dest_path=None,
        txt=None,
        pre_data=None,
        post_data=None,
    ):
        # post data is borked
        logging.debug(
            """ZOOM IMAGE: tl:{0} tt:{1}: tw:{2} th:{3}
lb_l:{4} lb_t:{5} lb_w:{6}, lb_h:{7}
zl:{8} zt:{9}""".format(
                target_left,
                target_top,
                target_width,
                target_height,
                lb_left,
                lb_top,
                lb_width,
                lb_height,
                zoom_left,
                zoom_top,
            )
        )
        if src_path and dest_path:
            img = self.book.add_image(src_path, dest_path, None)
        else:
            img = self.img
        tid = self.book.get_target_id()
        ordinal = self.book.get_ordinal()
        mag = Mag(
            txt,
            tid + self.PARENT_SUFFIX,
            tid,
            int(target_left),
            int(target_top),
            int(target_width),
            int(target_height),
            int(lb_left),
            int(lb_top),
            int(lb_width),
            int(lb_height),
            int(zoom_left),
            int(zoom_top),
            img.dest_path,
            ordinal,
            pre_data=pre_data,
            post_data=post_data,
            zoom_factor=zoom_factor,
        )
        self.mags.append(mag)

    def to_html(self):
        # temp = NewTextTemplate(PAGE_TEMPLATE)
        temp = self.book.loader.load("mobicomic2.html")
        stream = temp.generate(
            page=self,
            body="",
            img_src=self.img.dest_path,
            add_jquery=self.book.add_jquery,
        )
        html = stream.render("html", doctype="html-transitional")
        return html

    def add_html(self, dest_path):
        return self.book.add_html("", dest_path, self.to_html())


def test():
    with io.file("data/test.html", mode="r", encoding="utf8") as test_file:
        TEST_HTML = test_file.read()  # noqa

    book = MobiComicBook(add_jquery=True)
    title = "Test Comic35"
    book.set_title(title)
    cov_image = "data/little-nemo-19051015-l.jpeg"
    book.add_cover(cov_image, title=title)
    page = book.add_page()
    page.add_bg_image("data/little-nemo-19051015-l.jpeg", "img1.jpeg")
    # page.add_mag('foo_id_parent', 'foo_id', 20, 20, 30, 60, 30, 30)

    # target_left, target_top, target_width, target_height,
    page.auto_target(
        50,
        1 * 100.0 / 6,
        50,
        100.0 / 6,
        zoom_factor=3,
        post_data='<p class="textzoom">TEST DATA</p>',
    )

    for col in range(4):
        # target_left, target_top, target_width, target_height,
        page.auto_target(col * 25, 500.0 / 6, 25, 100.0 / 6, zoom_factor=2)

    h1 = page.add_html("1.html")
    book.add_spine_item(h1)

    page.add_bg_image("data/little-nemo-19051105-l.jpeg", "img3.jpeg")
    h3 = book.add_html("", "3.html", TEST_HTML)
    book.add_spine_item(h3)
    directory = "/tmp/mobitest"
    book.create_book(directory)
    book.create_archive(directory, directory + ".epub")


if __name__ == "__main__":
    test()
